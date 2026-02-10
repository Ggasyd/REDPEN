"""Exams routes - simplified for MVP."""

import hashlib
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_workspace_id, require_teacher
from app.models import (
    Exam,
    ExamTemplate,
    ExamVersion,
    Question,
    TemplateZone,
    User,
    WorkspaceMember,
)
from app.models.enums import QuestionType
from app.services.template_extraction import extract_template_zones_from_pdf
from app.utils.storage import storage

router = APIRouter()


class ExamCreate(BaseModel):
    title: str
    description: str | None = None
    subject: str | None = None
    grade_level: str | None = None


class ExamResponse(BaseModel):
    id: str
    title: str
    description: str | None
    subject: str | None

    class Config:
        from_attributes = True


class QuestionCreate(BaseModel):
    question_number: str
    question_text: str
    question_type: QuestionType
    max_points: float
    order_index: int


class TemplateUploadResponse(BaseModel):
    template_id: str
    exam_version_id: str
    template_hash: str
    original_filename: str
    page_count: int
    dpi: int
    is_active: bool


class TemplateExtractionRequest(BaseModel):
    overwrite_existing: bool = True
    pad_ratio: float = 0.10


class TemplateExtractionResponse(BaseModel):
    template_id: str
    page_count: int
    zones_created: int
    zones_deleted: int


class TemplateZoneBBox(BaseModel):
    x: int
    y: int
    width: int
    height: int


class TemplateZonePreview(BaseModel):
    id: str
    page_index: int
    question_key: str
    bbox: TemplateZoneBBox
    pad_ratio: float
    confidence: float | None
    source: str


class TemplateZonesPreviewResponse(BaseModel):
    template_id: str
    exam_version_id: str
    page_count: int
    dpi: int
    is_active: bool
    zones_count: int
    zones: list[TemplateZonePreview]


class TemplateZoneUpdateRequest(BaseModel):
    question_key: str | None = None
    page_index: int | None = None
    bbox_x: int | None = None
    bbox_y: int | None = None
    bbox_width: int | None = None
    bbox_height: int | None = None
    pad_ratio: float | None = None
    confidence: float | None = None
    is_validated: bool | None = None


class TemplateZonesBulkZoneUpdate(BaseModel):
    zone_id: str | None = None
    question_key: str
    page_index: int
    bbox_x: int
    bbox_y: int
    bbox_width: int
    bbox_height: int
    pad_ratio: float = 0.10
    confidence: float | None = None
    is_validated: bool = False


class TemplateZonesBulkUpsertRequest(BaseModel):
    zones: list[TemplateZonesBulkZoneUpdate]


class TemplateValidationResponse(BaseModel):
    template_id: str
    validated: bool
    zones_validated: int


def _serialize_zone(zone: TemplateZone) -> TemplateZonePreview:
    return TemplateZonePreview(
        id=str(zone.id),
        page_index=zone.page_index,
        question_key=zone.question_key,
        bbox=TemplateZoneBBox(
            x=zone.bbox_x,
            y=zone.bbox_y,
            width=zone.bbox_width,
            height=zone.bbox_height,
        ),
        pad_ratio=zone.pad_ratio,
        confidence=zone.confidence,
        source=zone.source,
    )


@router.post("/", response_model=ExamResponse, status_code=status.HTTP_201_CREATED)
async def create_exam(
    exam_data: ExamCreate,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Create a new exam."""
    exam = Exam(
        workspace_id=workspace_id,
        title=exam_data.title,
        description=exam_data.description,
        subject=exam_data.subject,
        grade_level=exam_data.grade_level,
    )
    db.add(exam)
    await db.flush()

    # Create version 1
    version = ExamVersion(
        exam_id=exam.id,
        version_number=1,
        is_active=True,
    )
    db.add(version)
    await db.commit()
    await db.refresh(exam)

    return ExamResponse(
        id=str(exam.id),
        title=exam.title,
        description=exam.description,
        subject=exam.subject,
    )


@router.post("/{exam_id}/versions")
async def create_exam_version(
    exam_id: UUID,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Create a new version of an exam."""
    # Get exam
    result = await db.execute(
        select(Exam).where(Exam.id == exam_id).where(Exam.workspace_id == workspace_id)
    )
    exam = result.scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    # Count existing versions
    result = await db.execute(select(ExamVersion).where(ExamVersion.exam_id == exam_id))
    versions = result.scalars().all()
    new_version_number = len(versions) + 1

    # Create new version
    version = ExamVersion(
        exam_id=exam_id,
        version_number=new_version_number,
        is_active=True,
    )
    db.add(version)
    await db.commit()

    return {"message": "Version created", "version_number": new_version_number}


@router.post("/versions/{version_id}/questions", status_code=status.HTTP_201_CREATED)
async def create_questions_bulk(
    version_id: UUID,
    questions: list[QuestionCreate],
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Create questions in bulk for an exam version."""
    # Verify version exists and belongs to workspace
    result = await db.execute(
        select(ExamVersion)
        .join(Exam)
        .where(ExamVersion.id == version_id)
        .where(Exam.workspace_id == workspace_id)
    )
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Exam version not found")

    # Create questions
    created_questions = []
    for q_data in questions:
        question = Question(
            exam_version_id=version_id,
            question_number=q_data.question_number,
            question_text=q_data.question_text,
            question_type=q_data.question_type,
            max_points=q_data.max_points,
            order_index=q_data.order_index,
        )
        db.add(question)
        created_questions.append(question)

    await db.commit()

    return {
        "message": f"Created {len(created_questions)} questions",
        "count": len(created_questions),
    }


@router.post(
    "/versions/{version_id}/templates",
    response_model=TemplateUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_exam_template(
    version_id: UUID,
    file: UploadFile = File(...),
    set_active: bool = True,
    dpi: int = 250,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Upload a template PDF for an exam version."""
    result = await db.execute(
        select(ExamVersion)
        .join(Exam)
        .where(ExamVersion.id == version_id)
        .where(Exam.workspace_id == workspace_id)
    )
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Exam version not found")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Template file must be a PDF")

    content_type = file.content_type or "application/pdf"
    if content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Template content type must be application/pdf",
        )

    if dpi < 72 or dpi > 600:
        raise HTTPException(status_code=400, detail="dpi must be between 72 and 600")

    file_content = await file.read()
    if not file_content:
        raise HTTPException(status_code=400, detail="Template file is empty")

    template_hash = hashlib.sha256(file_content).hexdigest()

    existing_result = await db.execute(
        select(ExamTemplate).where(
            ExamTemplate.exam_version_id == version_id,
            ExamTemplate.template_hash == template_hash,
        )
    )
    existing_template = existing_result.scalar_one_or_none()
    if existing_template:
        raise HTTPException(
            status_code=409,
            detail="Template already exists for this exam version",
        )

    storage_url = storage.upload_bytes(
        file_content,
        object_name=f"{version_id}/{template_hash}.pdf",
        content_type=content_type,
        folder="templates",
    )

    template = ExamTemplate(
        exam_version_id=version_id,
        template_hash=template_hash,
        original_filename=file.filename,
        storage_url=storage_url,
        content_type=content_type,
        file_size=len(file_content),
        page_count=0,
        dpi=dpi,
        metadata_json={"status": "uploaded"},
    )
    db.add(template)
    await db.flush()

    if set_active:
        version.active_template_id = template.id

    await db.commit()

    return TemplateUploadResponse(
        template_id=str(template.id),
        exam_version_id=str(version.id),
        template_hash=template.template_hash,
        original_filename=template.original_filename,
        page_count=template.page_count,
        dpi=template.dpi,
        is_active=version.active_template_id == template.id,
    )


@router.post(
    "/templates/{template_id}/extract-zones",
    response_model=TemplateExtractionResponse,
)
async def extract_template_zones(
    template_id: UUID,
    request: TemplateExtractionRequest,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Extract template zones from the uploaded PDF and persist them."""
    result = await db.execute(
        select(ExamTemplate)
        .join(ExamVersion, ExamVersion.id == ExamTemplate.exam_version_id)
        .join(Exam, Exam.id == ExamVersion.exam_id)
        .where(ExamTemplate.id == template_id)
        .where(Exam.workspace_id == workspace_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if request.pad_ratio < 0 or request.pad_ratio > 1:
        raise HTTPException(status_code=400, detail="pad_ratio must be between 0 and 1")

    try:
        pdf_bytes = storage.download_file(template.storage_url)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Failed to download template file"
        ) from exc

    try:
        page_count, extracted_zones = extract_template_zones_from_pdf(
            pdf_bytes,
            pad_ratio=request.pad_ratio,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail="Failed to extract zones from template"
        ) from exc

    zones_deleted = 0
    if request.overwrite_existing:
        existing_result = await db.execute(
            select(TemplateZone.id).where(TemplateZone.template_id == template.id)
        )
        existing_zone_ids = existing_result.scalars().all()
        zones_deleted = len(existing_zone_ids)

        await db.execute(
            TemplateZone.__table__.delete().where(TemplateZone.template_id == template.id)
        )

    for zone in extracted_zones:
        db.add(
            TemplateZone(
                template_id=template.id,
                page_index=zone["page_index"],
                question_key=zone["question_key"],
                bbox_x=zone["bbox_x"],
                bbox_y=zone["bbox_y"],
                bbox_width=zone["bbox_width"],
                bbox_height=zone["bbox_height"],
                pad_ratio=zone.get("pad_ratio", request.pad_ratio),
                confidence=zone.get("confidence"),
                source=zone.get("source", "auto_pymupdf"),
            )
        )

    metadata = dict(template.metadata_json or {})
    metadata["status"] = "extracted"
    metadata["zones_created"] = len(extracted_zones)
    metadata["extractor"] = "pymupdf"

    template.page_count = page_count
    template.metadata_json = metadata

    await db.commit()

    return TemplateExtractionResponse(
        template_id=str(template.id),
        page_count=template.page_count,
        zones_created=len(extracted_zones),
        zones_deleted=zones_deleted,
    )


@router.get(
    "/templates/{template_id}/zones",
    response_model=TemplateZonesPreviewResponse,
)
async def get_template_zones_preview(
    template_id: UUID,
    page: int | None = None,
    min_confidence: float | None = None,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Preview extracted zones for a template."""
    if page is not None and page < 0:
        raise HTTPException(status_code=400, detail="page must be >= 0")

    if min_confidence is not None and not (0 <= min_confidence <= 1):
        raise HTTPException(
            status_code=400,
            detail="min_confidence must be between 0 and 1",
        )

    template_result = await db.execute(
        select(ExamTemplate, ExamVersion.active_template_id)
        .join(ExamVersion, ExamVersion.id == ExamTemplate.exam_version_id)
        .join(Exam, Exam.id == ExamVersion.exam_id)
        .where(ExamTemplate.id == template_id)
        .where(Exam.workspace_id == workspace_id)
    )
    row = template_result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")

    template, active_template_id = row

    zones_query = (
        select(TemplateZone)
        .where(TemplateZone.template_id == template.id)
        .order_by(TemplateZone.page_index.asc(), TemplateZone.question_key.asc())
    )
    if page is not None:
        zones_query = zones_query.where(TemplateZone.page_index == page)
    if min_confidence is not None:
        zones_query = zones_query.where(TemplateZone.confidence >= min_confidence)

    zones_result = await db.execute(zones_query)
    zones = zones_result.scalars().all()

    return TemplateZonesPreviewResponse(
        template_id=str(template.id),
        exam_version_id=str(template.exam_version_id),
        page_count=template.page_count,
        dpi=template.dpi,
        is_active=active_template_id == template.id,
        zones_count=len(zones),
        zones=[_serialize_zone(zone) for zone in zones],
    )


@router.patch(
    "/template-zones/{zone_id}",
    response_model=TemplateZonePreview,
)
async def update_template_zone(
    zone_id: UUID,
    request: TemplateZoneUpdateRequest,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a single template zone after manual adjustment."""
    zone_result = await db.execute(
        select(TemplateZone)
        .join(ExamTemplate, ExamTemplate.id == TemplateZone.template_id)
        .join(ExamVersion, ExamVersion.id == ExamTemplate.exam_version_id)
        .join(Exam, Exam.id == ExamVersion.exam_id)
        .where(TemplateZone.id == zone_id)
        .where(Exam.workspace_id == workspace_id)
    )
    zone = zone_result.scalar_one_or_none()
    if zone is None:
        raise HTTPException(status_code=404, detail="Template zone not found")

    updates = request.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No changes provided")

    for key in ["bbox_x", "bbox_y"]:
        if key in updates and updates[key] < 0:
            raise HTTPException(status_code=400, detail=f"{key} must be >= 0")
    for key in ["bbox_width", "bbox_height"]:
        if key in updates and updates[key] <= 0:
            raise HTTPException(status_code=400, detail=f"{key} must be > 0")

    if "pad_ratio" in updates and not 0 <= updates["pad_ratio"] <= 1:
        raise HTTPException(status_code=400, detail="pad_ratio must be between 0 and 1")

    if "page_index" in updates and updates["page_index"] < 0:
        raise HTTPException(status_code=400, detail="page_index must be >= 0")

    if "confidence" in updates:
        confidence = updates["confidence"]
        if confidence is not None and not 0 <= confidence <= 1:
            raise HTTPException(status_code=400, detail="confidence must be between 0 and 1")

    for field, value in updates.items():
        setattr(zone, field, value)

    zone.source = "manual"
    zone.edit_source = "manual"
    zone.last_edited_by = current_user.id
    zone.last_edited_at = datetime.utcnow()

    if zone.is_validated:
        zone.validated_by = current_user.id
        zone.validated_at = datetime.utcnow()
    else:
        zone.validated_by = None
        zone.validated_at = None

    await db.commit()
    await db.refresh(zone)

    return _serialize_zone(zone)


@router.put(
    "/templates/{template_id}/zones",
    response_model=TemplateZonesPreviewResponse,
)
async def replace_template_zones(
    template_id: UUID,
    request: TemplateZonesBulkUpsertRequest,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Replace all zones for a template from teacher-edited coordinates."""
    template_result = await db.execute(
        select(ExamTemplate, ExamVersion.active_template_id)
        .join(ExamVersion, ExamVersion.id == ExamTemplate.exam_version_id)
        .join(Exam, Exam.id == ExamVersion.exam_id)
        .where(ExamTemplate.id == template_id)
        .where(Exam.workspace_id == workspace_id)
    )
    row = template_result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")

    template, active_template_id = row

    if not request.zones:
        raise HTTPException(status_code=400, detail="zones must not be empty")

    await db.execute(
        TemplateZone.__table__.delete().where(TemplateZone.template_id == template.id)
    )

    now = datetime.utcnow()
    for zone in request.zones:
        if zone.page_index < 0:
            raise HTTPException(status_code=400, detail="page_index must be >= 0")
        if zone.bbox_x < 0 or zone.bbox_y < 0:
            raise HTTPException(status_code=400, detail="bbox_x and bbox_y must be >= 0")
        if zone.bbox_width <= 0 or zone.bbox_height <= 0:
            raise HTTPException(status_code=400, detail="bbox_width and bbox_height must be > 0")
        if not 0 <= zone.pad_ratio <= 1:
            raise HTTPException(status_code=400, detail="pad_ratio must be between 0 and 1")
        if zone.confidence is not None and not 0 <= zone.confidence <= 1:
            raise HTTPException(status_code=400, detail="confidence must be between 0 and 1")

        db.add(
            TemplateZone(
                template_id=template.id,
                page_index=zone.page_index,
                question_key=zone.question_key,
                bbox_x=zone.bbox_x,
                bbox_y=zone.bbox_y,
                bbox_width=zone.bbox_width,
                bbox_height=zone.bbox_height,
                pad_ratio=zone.pad_ratio,
                confidence=zone.confidence,
                source="manual",
                edit_source="manual",
                last_edited_by=current_user.id,
                last_edited_at=now,
                is_validated=zone.is_validated,
                validated_by=current_user.id if zone.is_validated else None,
                validated_at=now if zone.is_validated else None,
            )
        )

    await db.flush()

    zones_result = await db.execute(
        select(TemplateZone)
        .where(TemplateZone.template_id == template.id)
        .order_by(TemplateZone.page_index.asc(), TemplateZone.question_key.asc())
    )
    zones = zones_result.scalars().all()

    metadata = dict(template.metadata_json or {})
    metadata["status"] = "edited"
    metadata["zones_created"] = len(zones)
    template.metadata_json = metadata

    await db.commit()

    return TemplateZonesPreviewResponse(
        template_id=str(template.id),
        exam_version_id=str(template.exam_version_id),
        page_count=template.page_count,
        dpi=template.dpi,
        is_active=active_template_id == template.id,
        zones_count=len(zones),
        zones=[_serialize_zone(zone) for zone in zones],
    )


@router.post(
    "/templates/{template_id}/validate",
    response_model=TemplateValidationResponse,
)
async def validate_template_zones(
    template_id: UUID,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Validate all zones for a template and mark it active for the exam version."""
    template_result = await db.execute(
        select(ExamTemplate, ExamVersion)
        .join(ExamVersion, ExamVersion.id == ExamTemplate.exam_version_id)
        .join(Exam, Exam.id == ExamVersion.exam_id)
        .where(ExamTemplate.id == template_id)
        .where(Exam.workspace_id == workspace_id)
    )
    row = template_result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")

    template, exam_version = row

    zones_result = await db.execute(
        select(TemplateZone).where(TemplateZone.template_id == template.id)
    )
    zones = zones_result.scalars().all()
    if not zones:
        raise HTTPException(status_code=400, detail="Template has no zones to validate")

    now = datetime.utcnow()
    for zone in zones:
        zone.is_validated = True
        zone.validated_by = current_user.id
        zone.validated_at = now
        zone.last_edited_by = current_user.id
        zone.last_edited_at = now
        if zone.edit_source != "manual":
            zone.edit_source = "auto"

    exam_version.active_template_id = template.id
    metadata = dict(template.metadata_json or {})
    metadata["status"] = "validated"
    template.metadata_json = metadata

    await db.commit()

    return TemplateValidationResponse(
        template_id=str(template.id),
        validated=True,
        zones_validated=len(zones),
    )

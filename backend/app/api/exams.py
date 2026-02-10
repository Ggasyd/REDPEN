"""Exams routes - simplified for MVP."""

import hashlib
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
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
    TemplateZoneRevision,
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


class TemplateZoneResponse(BaseModel):
    id: str
    template_id: str
    page_index: int
    question_key: str
    bbox_x: int
    bbox_y: int
    bbox_width: int
    bbox_height: int
    pad_ratio: float
    confidence: float | None
    source: str
    is_validated: bool
    validated_at: datetime | None
    validated_by: str | None
    last_edited_at: datetime | None
    last_edited_by: str | None
    edit_source: str


class TemplateZonePatch(BaseModel):
    page_index: int | None = None
    question_key: str | None = None
    bbox_x: int | None = None
    bbox_y: int | None = None
    bbox_width: int | None = None
    bbox_height: int | None = None
    pad_ratio: float | None = None
    confidence: float | None = None
    source: str | None = None
    is_validated: bool | None = None
    change_reason: str | None = None
    edit_source: str | None = None


class TemplateZoneExtractResponse(BaseModel):
    template_id: str
    page_count: int
    inserted_count: int
    zones: list[TemplateZoneResponse]


class TemplateZoneBulkPatchItem(BaseModel):
    zone_id: str
    page_index: int | None = None
    question_key: str | None = None
    bbox_x: int | None = None
    bbox_y: int | None = None
    bbox_width: int | None = None
    bbox_height: int | None = None
    pad_ratio: float | None = None
    confidence: float | None = None
    source: str | None = None
    is_validated: bool | None = None
    change_reason: str | None = None
    edit_source: str | None = None


class TemplateZonesBulkPatchRequest(BaseModel):
    items: list[TemplateZoneBulkPatchItem] = Field(default_factory=list)


class TemplateZonesBulkPatchResponse(BaseModel):
    template_id: str
    updated_count: int
    zones: list[TemplateZoneResponse]


class TemplateZonesValidateResponse(BaseModel):
    template_id: str
    validated_count: int
    invalid_zone_ids: list[str]
    status: str


class TemplateZonesResetResponse(BaseModel):
    template_id: str
    deleted_count: int
    status: str


def _zone_to_response(zone: TemplateZone) -> TemplateZoneResponse:
    return TemplateZoneResponse(
        id=str(zone.id),
        template_id=str(zone.template_id),
        page_index=zone.page_index,
        question_key=zone.question_key,
        bbox_x=zone.bbox_x,
        bbox_y=zone.bbox_y,
        bbox_width=zone.bbox_width,
        bbox_height=zone.bbox_height,
        pad_ratio=zone.pad_ratio,
        confidence=zone.confidence,
        source=zone.source,
        is_validated=zone.is_validated,
        validated_at=zone.validated_at,
        validated_by=(str(zone.validated_by) if zone.validated_by else None),
        last_edited_at=zone.last_edited_at,
        last_edited_by=(str(zone.last_edited_by) if zone.last_edited_by else None),
        edit_source=zone.edit_source,
    )



async def _create_zone_revision(
    db: AsyncSession,
    zone: TemplateZone,
    change_type: str,
    changed_by: UUID | None,
    change_reason: str | None = None,
) -> None:
    result = await db.execute(
        select(TemplateZoneRevision)
        .where(TemplateZoneRevision.zone_id == zone.id)
        .order_by(TemplateZoneRevision.revision_number.desc())
        .limit(1)
    )
    latest_revision = result.scalar_one_or_none()
    next_revision_number = (
        (latest_revision.revision_number + 1) if latest_revision else 1
    )

    revision = TemplateZoneRevision(
        zone_id=zone.id,
        template_id=zone.template_id,
        revision_number=next_revision_number,
        change_type=change_type,
        change_reason=change_reason,
        changed_by=changed_by,
        changed_at=datetime.now(UTC).replace(tzinfo=None),
        page_index=zone.page_index,
        question_key=zone.question_key,
        bbox_x=zone.bbox_x,
        bbox_y=zone.bbox_y,
        bbox_width=zone.bbox_width,
        bbox_height=zone.bbox_height,
        pad_ratio=zone.pad_ratio,
        confidence=zone.confidence,
        source=zone.source,
        is_validated=zone.is_validated,
        edit_source=zone.edit_source,
    )
    db.add(revision)


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
    "/templates/{template_id}/zones/extract",
    response_model=TemplateZoneExtractResponse,
)
async def extract_and_insert_template_zones(
    template_id: UUID,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Extract candidate zones from template PDF and persist them."""
    result = await db.execute(
        select(ExamTemplate)
        .join(ExamVersion, ExamTemplate.exam_version_id == ExamVersion.id)
        .join(Exam, ExamVersion.exam_id == Exam.id)
        .where(ExamTemplate.id == template_id)
        .where(Exam.workspace_id == workspace_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    pdf_bytes = storage.download_file(template.storage_url)
    page_count, extracted_zones = extract_template_zones_from_pdf(pdf_bytes)

    existing_result = await db.execute(
        select(TemplateZone).where(TemplateZone.template_id == template_id)
    )
    for zone in existing_result.scalars().all():
        await db.delete(zone)

    inserted_zones: list[TemplateZone] = []
    now = datetime.now(UTC).replace(tzinfo=None)
    for zone_data in extracted_zones:
        zone = TemplateZone(
            template_id=template_id,
            page_index=zone_data["page_index"],
            question_key=zone_data["question_key"],
            bbox_x=zone_data["bbox_x"],
            bbox_y=zone_data["bbox_y"],
            bbox_width=zone_data["bbox_width"],
            bbox_height=zone_data["bbox_height"],
            pad_ratio=zone_data.get("pad_ratio", 0.10),
            confidence=zone_data.get("confidence"),
            source=zone_data.get("source", "auto_pymupdf"),
            is_validated=False,
            last_edited_at=now,
            last_edited_by=current_user.id,
            edit_source="auto",
        )
        db.add(zone)
        await db.flush()
        await _create_zone_revision(
            db=db,
            zone=zone,
            change_type="extract_insert",
            changed_by=current_user.id,
            change_reason="automatic extraction",
        )
        inserted_zones.append(zone)

    template.page_count = page_count
    template.metadata_json = {
        **(template.metadata_json or {}),
        "status": "zones_extracted",
        "zones_detected": len(inserted_zones),
        "page_count": page_count,
        "extractor": "pymupdf",
        "extractor_version": (extracted_zones[0].get("extractor_version") if extracted_zones else "pymupdf_v2"),
    }
    await db.commit()

    return TemplateZoneExtractResponse(
        template_id=str(template.id),
        page_count=page_count,
        inserted_count=len(inserted_zones),
        zones=[_zone_to_response(zone) for zone in inserted_zones],
    )


@router.get("/templates/{template_id}/zones", response_model=list[TemplateZoneResponse])
async def get_template_zones_preview(
    template_id: UUID,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Preview zones for a template."""
    template_result = await db.execute(
        select(ExamTemplate)
        .join(ExamVersion, ExamTemplate.exam_version_id == ExamVersion.id)
        .join(Exam, ExamVersion.exam_id == Exam.id)
        .where(ExamTemplate.id == template_id)
        .where(Exam.workspace_id == workspace_id)
    )
    template = template_result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    zones_result = await db.execute(
        select(TemplateZone)
        .where(TemplateZone.template_id == template_id)
        .order_by(TemplateZone.page_index, TemplateZone.question_key)
    )
    zones = zones_result.scalars().all()
    return [_zone_to_response(zone) for zone in zones]



async def _apply_template_zone_patch(
    *,
    zone: TemplateZone,
    payload: TemplateZonePatch,
    current_user: User,
    db: AsyncSession,
) -> bool:
    changes_applied = False

    for field in [
        "page_index",
        "question_key",
        "bbox_x",
        "bbox_y",
        "bbox_width",
        "bbox_height",
        "pad_ratio",
        "confidence",
        "source",
    ]:
        new_value = getattr(payload, field)
        if new_value is not None and getattr(zone, field) != new_value:
            setattr(zone, field, new_value)
            changes_applied = True

    now = datetime.now(UTC).replace(tzinfo=None)
    if payload.is_validated is not None and payload.is_validated != zone.is_validated:
        zone.is_validated = payload.is_validated
        if payload.is_validated:
            zone.validated_at = now
            zone.validated_by = current_user.id
        else:
            zone.validated_at = None
            zone.validated_by = None
        changes_applied = True

    if payload.edit_source is not None:
        zone.edit_source = payload.edit_source
    elif changes_applied:
        zone.edit_source = "manual"

    if changes_applied:
        zone.last_edited_at = now
        zone.last_edited_by = current_user.id
        await db.flush()
        await _create_zone_revision(
            db=db,
            zone=zone,
            change_type="update",
            changed_by=current_user.id,
            change_reason=payload.change_reason,
        )

    return changes_applied


@router.patch(
    "/templates/{template_id}/zones/{zone_id}",
    response_model=TemplateZoneResponse,
)
async def patch_template_zone(
    template_id: UUID,
    zone_id: UUID,
    payload: TemplateZonePatch,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Adjust and/or validate a template zone."""
    template_result = await db.execute(
        select(ExamTemplate)
        .join(ExamVersion, ExamTemplate.exam_version_id == ExamVersion.id)
        .join(Exam, ExamVersion.exam_id == Exam.id)
        .where(ExamTemplate.id == template_id)
        .where(Exam.workspace_id == workspace_id)
    )
    template = template_result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    zone_result = await db.execute(
        select(TemplateZone)
        .where(TemplateZone.id == zone_id)
        .where(TemplateZone.template_id == template_id)
    )
    zone = zone_result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    changes_applied = await _apply_template_zone_patch(
        zone=zone,
        payload=payload,
        current_user=current_user,
        db=db,
    )

    if changes_applied:
        await db.commit()

    return _zone_to_response(zone)




@router.post(
    "/templates/{template_id}/zones/validate",
    response_model=TemplateZonesValidateResponse,
)
async def validate_template_zones(
    template_id: UUID,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Validate all coherent zones for a template."""
    template_result = await db.execute(
        select(ExamTemplate)
        .join(ExamVersion, ExamTemplate.exam_version_id == ExamVersion.id)
        .join(Exam, ExamVersion.exam_id == Exam.id)
        .where(ExamTemplate.id == template_id)
        .where(Exam.workspace_id == workspace_id)
    )
    template = template_result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    zones_result = await db.execute(
        select(TemplateZone).where(TemplateZone.template_id == template_id)
    )
    zones = zones_result.scalars().all()

    invalid_zone_ids: list[str] = []
    validated_count = 0
    now = datetime.now(UTC).replace(tzinfo=None)
    for zone in zones:
        is_bbox_valid = zone.bbox_width > 0 and zone.bbox_height > 0
        is_page_valid = zone.page_index >= 0 and zone.page_index < max(1, template.page_count)
        if not is_bbox_valid or not is_page_valid:
            invalid_zone_ids.append(str(zone.id))
            continue

        if not zone.is_validated:
            zone.is_validated = True
            zone.validated_at = now
            zone.validated_by = current_user.id
            zone.last_edited_at = now
            zone.last_edited_by = current_user.id
            zone.edit_source = "manual"
            await db.flush()
            await _create_zone_revision(
                db=db,
                zone=zone,
                change_type="bulk_validate",
                changed_by=current_user.id,
                change_reason="bulk validation",
            )
            validated_count += 1

    template.metadata_json = {
        **(template.metadata_json or {}),
        "status": "zones_validated",
        "zones_validated": sum(1 for zone in zones if zone.is_validated),
        "zones_invalid": len(invalid_zone_ids),
    }

    await db.commit()

    return TemplateZonesValidateResponse(
        template_id=str(template.id),
        validated_count=validated_count,
        invalid_zone_ids=invalid_zone_ids,
        status="zones_validated",
    )


@router.post(
    "/templates/{template_id}/zones/reset",
    response_model=TemplateZonesResetResponse,
)
async def reset_template_zones(
    template_id: UUID,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Reset extracted zones for a template."""
    template_result = await db.execute(
        select(ExamTemplate)
        .join(ExamVersion, ExamTemplate.exam_version_id == ExamVersion.id)
        .join(Exam, ExamVersion.exam_id == Exam.id)
        .where(ExamTemplate.id == template_id)
        .where(Exam.workspace_id == workspace_id)
    )
    template = template_result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    zones_result = await db.execute(
        select(TemplateZone).where(TemplateZone.template_id == template_id)
    )
    zones = zones_result.scalars().all()
    deleted_count = len(zones)

    for zone in zones:
        await db.delete(zone)

    template.metadata_json = {
        **(template.metadata_json or {}),
        "status": "uploaded",
        "zones_detected": 0,
        "zones_validated": 0,
    }

    await db.commit()

    return TemplateZonesResetResponse(
        template_id=str(template.id),
        deleted_count=deleted_count,
        status="uploaded",
    )


@router.patch(
    "/templates/{template_id}/zones",
    response_model=TemplateZonesBulkPatchResponse,
)
async def bulk_patch_template_zones(
    template_id: UUID,
    payload: TemplateZonesBulkPatchRequest,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bulk adjust template zones in a single request."""
    template_result = await db.execute(
        select(ExamTemplate)
        .join(ExamVersion, ExamTemplate.exam_version_id == ExamVersion.id)
        .join(Exam, ExamVersion.exam_id == Exam.id)
        .where(ExamTemplate.id == template_id)
        .where(Exam.workspace_id == workspace_id)
    )
    template = template_result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    updated_zones: list[TemplateZone] = []
    updated_count = 0
    for item in payload.items:
        zone_result = await db.execute(
            select(TemplateZone)
            .where(TemplateZone.id == UUID(item.zone_id))
            .where(TemplateZone.template_id == template_id)
        )
        zone = zone_result.scalar_one_or_none()
        if not zone:
            raise HTTPException(status_code=404, detail=f"Zone not found: {item.zone_id}")

        patch_payload = TemplateZonePatch(**item.model_dump(exclude={"zone_id"}))
        changes_applied = await _apply_template_zone_patch(
            zone=zone,
            payload=patch_payload,
            current_user=current_user,
            db=db,
        )
        if changes_applied:
            updated_count += 1
        updated_zones.append(zone)

    if updated_count:
        await db.commit()

    return TemplateZonesBulkPatchResponse(
        template_id=str(template.id),
        updated_count=updated_count,
        zones=[_zone_to_response(zone) for zone in updated_zones],
    )


@router.put(
    "/templates/{template_id}/zones/{zone_id}",
    response_model=TemplateZoneResponse,
)
async def put_template_zone(
    template_id: UUID,
    zone_id: UUID,
    payload: TemplateZonePatch,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """PUT alias for updating/validating a template zone."""
    return await patch_template_zone(
        template_id=template_id,
        zone_id=zone_id,
        payload=payload,
        workspace_id=workspace_id,
        membership=membership,
        current_user=current_user,
        db=db,
    )

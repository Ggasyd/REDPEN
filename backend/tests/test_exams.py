"""Exam endpoint tests."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Exam,
    ExamTemplate,
    ExamVersion,
    TemplateZone,
    TemplateZoneRevision,
    User,
)
from app.models.enums import QuestionType, WorkspaceRole
from app.utils.security import hash_password
from tests.utils import AsyncClient


@pytest.mark.asyncio
async def test_create_exam_and_version(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
):
    user = User(
        email="exam-teacher@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="Exam Workspace")
    db_session.add_all([user, workspace])
    await db_session.flush()
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.TEACHER
    )
    db_session.add(membership)
    await db_session.commit()

    response = await client.post(
        "/api/exams/",
        json={"title": "Midterm", "subject": "Math"},
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )
    assert response.status_code == 201
    exam_id = response.json()["id"]

    response = await client.post(
        f"/api/exams/{exam_id}/versions",
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )
    assert response.status_code == 200
    assert response.json()["version_number"] == 2


@pytest.mark.asyncio
async def test_create_questions_bulk_requires_workspace_match(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
):
    user = User(
        email="question-teacher@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="Question Workspace")
    other_workspace = workspace_factory(name="Other Workspace")
    db_session.add_all([user, workspace, other_workspace])
    await db_session.flush()
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.TEACHER
    )
    db_session.add(membership)
    await db_session.commit()

    exam = Exam(workspace_id=workspace.id, title="Quiz")
    db_session.add(exam)
    await db_session.flush()
    version = ExamVersion(exam_id=exam.id, version_number=1, is_active=True)
    db_session.add(version)
    await db_session.commit()

    response = await client.post(
        f"/api/exams/versions/{version.id}/questions",
        json=[
            {
                "question_number": "1",
                "question_text": "What is 2+2?",
                "question_type": QuestionType.OPEN.value,
                "max_points": 2,
                "order_index": 1,
            }
        ],
        headers={**auth_headers(user), "X-Workspace-Id": str(other_workspace.id)},
    )

    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_exam_template_success(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
    monkeypatch,
):
    user = User(
        email="template-teacher@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="Template Workspace")
    db_session.add_all([user, workspace])
    await db_session.flush()
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.TEACHER
    )
    db_session.add(membership)
    await db_session.flush()

    exam = Exam(workspace_id=workspace.id, title="Template Exam")
    db_session.add(exam)
    await db_session.flush()
    version = ExamVersion(exam_id=exam.id, version_number=1, is_active=True)
    db_session.add(version)
    await db_session.commit()

    from app.utils import storage as storage_module

    monkeypatch.setattr(
        storage_module.storage,
        "upload_bytes",
        lambda *args, **kwargs: "bucket/templates/path.pdf",
    )

    response = await client.post(
        f"/api/exams/versions/{version.id}/templates",
        files={"file": ("template.pdf", b"%PDF-template", "application/pdf")},
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["exam_version_id"] == str(version.id)
    assert payload["original_filename"] == "template.pdf"
    assert payload["is_active"] is True

    from uuid import UUID

    template_result = await db_session.get(ExamTemplate, UUID(payload["template_id"]))
    assert template_result is not None


@pytest.mark.asyncio
async def test_upload_exam_template_requires_pdf_content_type(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
):
    user = User(
        email="template-validation@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="Template Validation Workspace")
    db_session.add_all([user, workspace])
    await db_session.flush()
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.TEACHER
    )
    db_session.add(membership)
    await db_session.flush()

    exam = Exam(workspace_id=workspace.id, title="Template Exam")
    db_session.add(exam)
    await db_session.flush()
    version = ExamVersion(exam_id=exam.id, version_number=1, is_active=True)
    db_session.add(version)
    await db_session.commit()

    response = await client.post(
        f"/api/exams/versions/{version.id}/templates",
        files={"file": ("template.txt", b"not-pdf", "text/plain")},
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


@pytest.mark.asyncio
async def test_extract_and_preview_template_zones(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
    monkeypatch,
):
    user = User(
        email="zones-teacher@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="Zones Workspace")
    db_session.add_all([user, workspace])
    await db_session.flush()
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.TEACHER
    )
    db_session.add(membership)
    await db_session.flush()

    exam = Exam(workspace_id=workspace.id, title="Zones Exam")
    db_session.add(exam)
    await db_session.flush()
    version = ExamVersion(exam_id=exam.id, version_number=1, is_active=True)
    db_session.add(version)
    await db_session.flush()
    template = ExamTemplate(
        exam_version_id=version.id,
        template_hash="abc123",
        original_filename="template.pdf",
        storage_url="bucket/templates/template.pdf",
        content_type="application/pdf",
        file_size=123,
        page_count=0,
        dpi=250,
        metadata_json={"status": "uploaded"},
    )
    db_session.add(template)
    await db_session.commit()

    from app.api import exams as exams_api
    from app.utils import storage as storage_module

    monkeypatch.setattr(storage_module.storage, "download_file", lambda *args, **kwargs: b"%PDF")
    monkeypatch.setattr(
        exams_api,
        "extract_template_zones_from_pdf",
        lambda *_args, **_kwargs: (
            2,
            [
                {
                    "page_index": 0,
                    "question_key": "Q1",
                    "bbox_x": 10,
                    "bbox_y": 20,
                    "bbox_width": 300,
                    "bbox_height": 120,
                    "pad_ratio": 0.1,
                    "confidence": 0.9,
                    "source": "auto_pymupdf",
                }
            ],
        ),
    )

    extract_response = await client.post(
        f"/api/exams/templates/{template.id}/zones/extract",
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )
    assert extract_response.status_code == 200
    extract_payload = extract_response.json()
    assert extract_payload["inserted_count"] == 1
    assert extract_payload["page_count"] == 2
    assert extract_payload["zones"][0]["question_key"] == "Q1"

    preview_response = await client.get(
        f"/api/exams/templates/{template.id}/zones",
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert len(preview_payload) == 1
    assert preview_payload[0]["question_key"] == "Q1"

    zone_result = await db_session.execute(
        select(TemplateZone).where(TemplateZone.template_id == template.id)
    )
    zone = zone_result.scalar_one_or_none()
    assert zone is not None

    revision_result = await db_session.execute(
        select(TemplateZoneRevision).where(TemplateZoneRevision.zone_id == zone.id)
    )
    revision = revision_result.scalar_one_or_none()
    assert revision is not None
    assert revision.change_type == "extract_insert"


@pytest.mark.asyncio
async def test_patch_zone_updates_validation_and_creates_revision(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
):
    user = User(
        email="zones-update@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="Zones Update Workspace")
    db_session.add_all([user, workspace])
    await db_session.flush()
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.TEACHER
    )
    db_session.add(membership)
    await db_session.flush()

    exam = Exam(workspace_id=workspace.id, title="Zones Exam")
    db_session.add(exam)
    await db_session.flush()
    version = ExamVersion(exam_id=exam.id, version_number=1, is_active=True)
    db_session.add(version)
    await db_session.flush()
    template = ExamTemplate(
        exam_version_id=version.id,
        template_hash="abc124",
        original_filename="template.pdf",
        storage_url="bucket/templates/template2.pdf",
        content_type="application/pdf",
        file_size=321,
        page_count=1,
        dpi=250,
        metadata_json={"status": "zones_extracted"},
    )
    db_session.add(template)
    await db_session.flush()

    zone = TemplateZone(
        template_id=template.id,
        page_index=0,
        question_key="Q1",
        bbox_x=10,
        bbox_y=10,
        bbox_width=100,
        bbox_height=100,
        pad_ratio=0.1,
        confidence=0.8,
        source="auto_pymupdf",
        is_validated=False,
        edit_source="auto",
    )
    db_session.add(zone)
    await db_session.commit()

    response = await client.patch(
        f"/api/exams/templates/{template.id}/zones/{zone.id}",
        json={
            "bbox_x": 15,
            "bbox_y": 25,
            "is_validated": True,
            "change_reason": "manual adjust",
            "edit_source": "manual",
        },
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["bbox_x"] == 15
    assert payload["bbox_y"] == 25
    assert payload["is_validated"] is True
    assert payload["edit_source"] == "manual"

    zone_db = await db_session.get(TemplateZone, zone.id)
    assert zone_db is not None
    assert zone_db.validated_by == user.id
    assert zone_db.validated_at is not None

    revision_result = await db_session.execute(
        select(TemplateZoneRevision)
        .where(TemplateZoneRevision.zone_id == zone.id)
        .order_by(TemplateZoneRevision.revision_number)
    )
    revisions = revision_result.scalars().all()
    assert len(revisions) == 1
    assert revisions[0].change_type == "update"


@pytest.mark.asyncio
async def test_validate_template_zones_marks_valid_and_updates_metadata(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
):
    user = User(
        email="zones-validate@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="Zones Validate Workspace")
    db_session.add_all([user, workspace])
    await db_session.flush()
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.TEACHER
    )
    db_session.add(membership)
    await db_session.flush()

    exam = Exam(workspace_id=workspace.id, title="Zones Exam")
    db_session.add(exam)
    await db_session.flush()
    version = ExamVersion(exam_id=exam.id, version_number=1, is_active=True)
    db_session.add(version)
    await db_session.flush()
    template = ExamTemplate(
        exam_version_id=version.id,
        template_hash="abc125",
        original_filename="template.pdf",
        storage_url="bucket/templates/template3.pdf",
        content_type="application/pdf",
        file_size=100,
        page_count=1,
        dpi=250,
        metadata_json={"status": "zones_extracted"},
    )
    db_session.add(template)
    await db_session.flush()

    valid_zone = TemplateZone(
        template_id=template.id,
        page_index=0,
        question_key="Q1",
        bbox_x=20,
        bbox_y=20,
        bbox_width=150,
        bbox_height=80,
        pad_ratio=0.1,
        confidence=0.8,
        source="auto_pymupdf",
        is_validated=False,
        edit_source="auto",
    )
    invalid_zone = TemplateZone(
        template_id=template.id,
        page_index=99,
        question_key="Q2",
        bbox_x=20,
        bbox_y=120,
        bbox_width=150,
        bbox_height=80,
        pad_ratio=0.1,
        confidence=0.8,
        source="auto_pymupdf",
        is_validated=False,
        edit_source="auto",
    )
    db_session.add_all([valid_zone, invalid_zone])
    await db_session.commit()

    response = await client.post(
        f"/api/exams/templates/{template.id}/zones/validate",
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["validated_count"] == 1
    assert payload["status"] == "zones_validated"
    assert str(invalid_zone.id) in payload["invalid_zone_ids"]

    zone_db = await db_session.get(TemplateZone, valid_zone.id)
    assert zone_db is not None
    assert zone_db.is_validated is True
    assert zone_db.validated_by == user.id

    template_db = await db_session.get(ExamTemplate, template.id)
    assert template_db is not None
    assert template_db.metadata_json["status"] == "zones_validated"


@pytest.mark.asyncio
async def test_bulk_patch_and_reset_template_zones(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
):
    user = User(
        email="zones-bulk@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="Zones Bulk Workspace")
    db_session.add_all([user, workspace])
    await db_session.flush()
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.TEACHER
    )
    db_session.add(membership)
    await db_session.flush()

    exam = Exam(workspace_id=workspace.id, title="Zones Exam")
    db_session.add(exam)
    await db_session.flush()
    version = ExamVersion(exam_id=exam.id, version_number=1, is_active=True)
    db_session.add(version)
    await db_session.flush()
    template = ExamTemplate(
        exam_version_id=version.id,
        template_hash="abc126",
        original_filename="template.pdf",
        storage_url="bucket/templates/template4.pdf",
        content_type="application/pdf",
        file_size=200,
        page_count=1,
        dpi=250,
        metadata_json={"status": "zones_extracted"},
    )
    db_session.add(template)
    await db_session.flush()

    zone = TemplateZone(
        template_id=template.id,
        page_index=0,
        question_key="Q1",
        bbox_x=10,
        bbox_y=10,
        bbox_width=100,
        bbox_height=100,
        pad_ratio=0.1,
        confidence=0.8,
        source="auto_pymupdf",
        is_validated=False,
        edit_source="auto",
    )
    db_session.add(zone)
    await db_session.commit()

    bulk_response = await client.patch(
        f"/api/exams/templates/{template.id}/zones",
        json={
            "items": [
                {
                    "zone_id": str(zone.id),
                    "bbox_x": 42,
                    "bbox_y": 52,
                    "change_reason": "bulk adjust",
                    "edit_source": "manual",
                }
            ]
        },
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert bulk_response.status_code == 200
    bulk_payload = bulk_response.json()
    assert bulk_payload["updated_count"] == 1
    assert bulk_payload["zones"][0]["bbox_x"] == 42
    assert bulk_payload["zones"][0]["last_edited_by"] == str(user.id)

    reset_response = await client.post(
        f"/api/exams/templates/{template.id}/zones/reset",
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert reset_response.status_code == 200
    reset_payload = reset_response.json()
    assert reset_payload["deleted_count"] == 1

    zone_result = await db_session.execute(
        select(TemplateZone).where(TemplateZone.template_id == template.id)
    )
    assert zone_result.scalars().all() == []

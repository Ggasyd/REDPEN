"""Exam endpoint tests."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Exam, ExamTemplate, ExamVersion, TemplateZone, User
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
async def test_extract_template_zones_success(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
    monkeypatch,
):
    user = User(
        email="template-extract@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="Extract Workspace")
    db_session.add_all([user, workspace])
    await db_session.flush()
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.TEACHER
    )
    db_session.add(membership)
    await db_session.flush()

    exam = Exam(workspace_id=workspace.id, title="Extraction Exam")
    db_session.add(exam)
    await db_session.flush()
    version = ExamVersion(exam_id=exam.id, version_number=1, is_active=True)
    db_session.add(version)
    await db_session.flush()

    template = ExamTemplate(
        exam_version_id=version.id,
        template_hash="hash-1",
        original_filename="template.pdf",
        storage_url="bucket/templates/template.pdf",
        content_type="application/pdf",
        file_size=128,
        page_count=0,
        dpi=250,
        metadata_json={"status": "uploaded"},
    )
    db_session.add(template)
    await db_session.commit()

    from app.api import exams as exams_api
    from app.utils import storage as storage_module

    monkeypatch.setattr(
        storage_module.storage, "download_file", lambda *_: b"%PDF-test"
    )
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
                    "bbox_width": 100,
                    "bbox_height": 80,
                    "pad_ratio": 0.1,
                    "confidence": 0.9,
                    "source": "auto_pymupdf",
                },
                {
                    "page_index": 1,
                    "question_key": "Q2",
                    "bbox_x": 11,
                    "bbox_y": 21,
                    "bbox_width": 101,
                    "bbox_height": 81,
                    "pad_ratio": 0.1,
                    "confidence": 0.8,
                    "source": "auto_pymupdf",
                },
            ],
        ),
    )

    response = await client.post(
        f"/api/exams/templates/{template.id}/extract-zones",
        json={"overwrite_existing": True, "pad_ratio": 0.1},
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["page_count"] == 2
    assert payload["zones_created"] == 2
    assert payload["zones_deleted"] == 0


@pytest.mark.asyncio
async def test_extract_template_zones_overwrites_existing(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
    monkeypatch,
):
    user = User(
        email="template-overwrite@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="Overwrite Workspace")
    db_session.add_all([user, workspace])
    await db_session.flush()
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.TEACHER
    )
    db_session.add(membership)
    await db_session.flush()

    exam = Exam(workspace_id=workspace.id, title="Extraction Exam")
    db_session.add(exam)
    await db_session.flush()
    version = ExamVersion(exam_id=exam.id, version_number=1, is_active=True)
    db_session.add(version)
    await db_session.flush()

    template = ExamTemplate(
        exam_version_id=version.id,
        template_hash="hash-2",
        original_filename="template.pdf",
        storage_url="bucket/templates/template.pdf",
        content_type="application/pdf",
        file_size=256,
        page_count=0,
        dpi=250,
        metadata_json={"status": "uploaded"},
    )
    db_session.add(template)
    await db_session.flush()

    db_session.add(
        TemplateZone(
            template_id=template.id,
            page_index=0,
            question_key="Q-OLD",
            bbox_x=0,
            bbox_y=0,
            bbox_width=10,
            bbox_height=10,
            pad_ratio=0.1,
            confidence=0.5,
            source="manual",
        )
    )
    await db_session.commit()

    from app.api import exams as exams_api
    from app.utils import storage as storage_module

    monkeypatch.setattr(
        storage_module.storage, "download_file", lambda *_: b"%PDF-test"
    )
    monkeypatch.setattr(
        exams_api,
        "extract_template_zones_from_pdf",
        lambda *_args, **_kwargs: (
            1,
            [
                {
                    "page_index": 0,
                    "question_key": "Q1",
                    "bbox_x": 100,
                    "bbox_y": 200,
                    "bbox_width": 300,
                    "bbox_height": 400,
                    "pad_ratio": 0.2,
                    "confidence": 0.95,
                    "source": "auto_pymupdf",
                }
            ],
        ),
    )

    response = await client.post(
        f"/api/exams/templates/{template.id}/extract-zones",
        json={"overwrite_existing": True, "pad_ratio": 0.2},
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["zones_created"] == 1
    assert payload["zones_deleted"] == 1

    from sqlalchemy import select

    result = await db_session.execute(
        select(TemplateZone).where(TemplateZone.template_id == template.id)
    )
    zones = result.scalars().all()
    assert len(zones) == 1
    assert zones[0].question_key == "Q1"


@pytest.mark.asyncio
async def test_get_template_zones_preview_success(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
):
    user = User(
        email="template-preview@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="Preview Workspace")
    db_session.add_all([user, workspace])
    await db_session.flush()
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.TEACHER
    )
    db_session.add(membership)
    await db_session.flush()

    exam = Exam(workspace_id=workspace.id, title="Preview Exam")
    db_session.add(exam)
    await db_session.flush()
    version = ExamVersion(exam_id=exam.id, version_number=1, is_active=True)
    db_session.add(version)
    await db_session.flush()

    template = ExamTemplate(
        exam_version_id=version.id,
        template_hash="preview-hash",
        original_filename="template.pdf",
        storage_url="bucket/templates/template.pdf",
        content_type="application/pdf",
        file_size=256,
        page_count=2,
        dpi=250,
        metadata_json={"status": "extracted"},
    )
    db_session.add(template)
    await db_session.flush()

    version.active_template_id = template.id

    db_session.add_all(
        [
            TemplateZone(
                template_id=template.id,
                page_index=0,
                question_key="Q2",
                bbox_x=20,
                bbox_y=40,
                bbox_width=100,
                bbox_height=80,
                pad_ratio=0.1,
                confidence=0.8,
                source="auto_pymupdf",
            ),
            TemplateZone(
                template_id=template.id,
                page_index=0,
                question_key="Q1",
                bbox_x=10,
                bbox_y=20,
                bbox_width=90,
                bbox_height=70,
                pad_ratio=0.1,
                confidence=0.95,
                source="manual",
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(
        f"/api/exams/templates/{template.id}/zones",
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["template_id"] == str(template.id)
    assert payload["is_active"] is True
    assert payload["zones_count"] == 2
    assert [zone["question_key"] for zone in payload["zones"]] == ["Q1", "Q2"]
    assert payload["zones"][0]["bbox"] == {"x": 10, "y": 20, "width": 90, "height": 70}


@pytest.mark.asyncio
async def test_get_template_zones_preview_filters_and_validation(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
):
    user = User(
        email="template-preview-filters@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="Preview Filters Workspace")
    db_session.add_all([user, workspace])
    await db_session.flush()
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.TEACHER
    )
    db_session.add(membership)
    await db_session.flush()

    exam = Exam(workspace_id=workspace.id, title="Preview Exam")
    db_session.add(exam)
    await db_session.flush()
    version = ExamVersion(exam_id=exam.id, version_number=1, is_active=True)
    db_session.add(version)
    await db_session.flush()

    template = ExamTemplate(
        exam_version_id=version.id,
        template_hash="preview-filter-hash",
        original_filename="template.pdf",
        storage_url="bucket/templates/template.pdf",
        content_type="application/pdf",
        file_size=128,
        page_count=2,
        dpi=300,
        metadata_json={"status": "extracted"},
    )
    db_session.add(template)
    await db_session.flush()

    db_session.add_all(
        [
            TemplateZone(
                template_id=template.id,
                page_index=0,
                question_key="Q1",
                bbox_x=0,
                bbox_y=0,
                bbox_width=50,
                bbox_height=50,
                pad_ratio=0.1,
                confidence=0.7,
                source="auto_pymupdf",
            ),
            TemplateZone(
                template_id=template.id,
                page_index=1,
                question_key="Q2",
                bbox_x=100,
                bbox_y=100,
                bbox_width=60,
                bbox_height=60,
                pad_ratio=0.1,
                confidence=0.95,
                source="auto_pymupdf",
            ),
        ]
    )
    await db_session.commit()

    filtered_response = await client.get(
        f"/api/exams/templates/{template.id}/zones?page=1&min_confidence=0.9",
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert filtered_response.status_code == 200
    filtered_payload = filtered_response.json()
    assert filtered_payload["zones_count"] == 1
    assert filtered_payload["zones"][0]["question_key"] == "Q2"

    invalid_response = await client.get(
        f"/api/exams/templates/{template.id}/zones?min_confidence=1.1",
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert invalid_response.status_code == 400
    assert "min_confidence" in invalid_response.json()["detail"]

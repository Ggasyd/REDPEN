"""Exam endpoint tests."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Exam, ExamTemplate, ExamVersion, User
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

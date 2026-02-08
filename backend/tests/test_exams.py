"""Exam endpoint tests."""
import pytest
from tests.utils import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Exam, ExamVersion, User
from app.models.enums import QuestionType, WorkspaceRole
from app.utils.security import hash_password


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

    assert response.status_code == 404
    assert "Exam version not found" in response.json()["detail"]

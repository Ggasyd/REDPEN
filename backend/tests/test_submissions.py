"""Submission endpoint tests."""
import importlib.util
import pytest
from tests.utils import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Exam, ExamVersion, Submission, User
from app.models.enums import WorkspaceRole
from app.utils.security import hash_password


@pytest.mark.asyncio
async def test_upload_submission_requires_exam_version(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
):
    user = User(
        email="upload-required@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="Upload Workspace")
    db_session.add_all([user, workspace])
    await db_session.flush()
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.TEACHER
    )
    db_session.add(membership)
    await db_session.commit()

    response = await client.post(
        "/api/submissions/",
        files={"file": ("test.pdf", b"PDF", "application/pdf")},
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert response.status_code == 400
    assert "exam_version_id required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_submission_success(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
    monkeypatch,
):
    user = User(
        email="upload@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="Submission Workspace")
    db_session.add_all([user, workspace])
    await db_session.flush()
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.TEACHER
    )
    db_session.add(membership)
    await db_session.flush()

    exam = Exam(workspace_id=workspace.id, title="Final")
    db_session.add(exam)
    await db_session.flush()
    version = ExamVersion(exam_id=exam.id, version_number=1, is_active=True)
    db_session.add(version)
    await db_session.commit()

    from app.utils import storage as storage_module
    from app.workers import tasks as task_module

    monkeypatch.setattr(
        storage_module.storage, "upload_bytes", lambda *args, **kwargs: "bucket/path"
    )
    monkeypatch.setattr(task_module.process_submission_task, "delay", lambda *_: None)

    if importlib.util.find_spec("multipart") is None:
        pytest.skip("python-multipart is required for file upload tests")

    response = await client.post(
        "/api/submissions/",
        params={"exam_version_id": str(version.id)},
        files={"file": ("test.pdf", b"PDF", "application/pdf")},
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["original_filename"] == "test.pdf"


@pytest.mark.asyncio
async def test_get_submission_isolated_by_workspace(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
):
    user = User(
        email="submission-owner@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="Main Workspace")
    other_workspace = workspace_factory(name="Other Workspace")
    db_session.add_all([user, workspace, other_workspace])
    await db_session.flush()
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.TEACHER
    )
    db_session.add(membership)
    await db_session.flush()

    exam = Exam(workspace_id=workspace.id, title="Assessment")
    db_session.add(exam)
    await db_session.flush()
    version = ExamVersion(exam_id=exam.id, version_number=1, is_active=True)
    db_session.add(version)
    await db_session.flush()
    submission = Submission(
        workspace_id=workspace.id,
        exam_version_id=version.id,
        original_filename="file.pdf",
        storage_url="bucket/path",
    )
    db_session.add(submission)
    await db_session.commit()

    response = await client.get(
        f"/api/submissions/{submission.id}",
        headers={**auth_headers(user), "X-Workspace-Id": str(other_workspace.id)},
    )

    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]

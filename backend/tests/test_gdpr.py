"""GDPR endpoint tests."""
import pytest
from tests.utils import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Classroom, Student, User, WorkspaceSettings
from app.models.enums import RetentionMode, WorkspaceRole
from app.utils.security import hash_password


@pytest.mark.asyncio
async def test_get_retention_settings_requires_admin(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
):
    user = User(
        email="admin@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="GDPR Workspace")
    db_session.add_all([user, workspace])
    await db_session.flush()
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.ADMIN
    )
    settings = WorkspaceSettings(workspace_id=workspace.id)
    db_session.add_all([membership, settings])
    await db_session.commit()

    response = await client.get(
        "/api/gdpr/settings/retention",
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["retention_submissions_days"] == settings.retention_submissions_days


@pytest.mark.asyncio
async def test_update_retention_settings_owner_only(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
):
    user = User(
        email="owner@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="Owner Workspace")
    db_session.add_all([user, workspace])
    await db_session.flush()
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.OWNER
    )
    settings = WorkspaceSettings(workspace_id=workspace.id)
    db_session.add_all([membership, settings])
    await db_session.commit()

    response = await client.patch(
        "/api/gdpr/settings/retention",
        json={"retention_submissions_days": 365},
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Settings updated"


@pytest.mark.asyncio
async def test_run_retention_enforcement_triggers_task(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
    monkeypatch,
):
    user = User(
        email="retention@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="Retention Workspace")
    db_session.add_all([user, workspace])
    await db_session.flush()
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.OWNER
    )
    db_session.add(membership)
    await db_session.commit()

    called = {"count": 0}

    from app.workers import tasks as task_module

    def _fake_delay(_):
        called["count"] += 1

    monkeypatch.setattr(task_module.retention_enforcement_task, "delay", _fake_delay)

    response = await client.post(
        "/api/gdpr/retention/run",
        params={"mode": RetentionMode.PREVIEW.value},
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert response.status_code == 200
    assert called["count"] == 1


@pytest.mark.asyncio
async def test_anonymize_student(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
):
    user = User(
        email="anonymize@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="Privacy Workspace")
    db_session.add_all([user, workspace])
    await db_session.flush()
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.ADMIN
    )
    classroom = Classroom(workspace_id=workspace.id, name="Privacy Class")
    student = Student(
        workspace_id=workspace.id,
        classroom_id=classroom.id,
        first_name="Jane",
        last_name="Doe",
        display_name="Jane Doe",
    )
    db_session.add_all([membership, classroom, student])
    await db_session.commit()

    response = await client.post(
        f"/api/gdpr/student/{student.id}/anonymize",
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert response.status_code == 200
    assert response.json()["student_id"] == str(student.id)

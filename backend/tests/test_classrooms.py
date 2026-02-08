"""Classroom endpoint tests."""
import pytest
from tests.utils import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Classroom, Student, User, WorkspaceMember
from app.models.enums import WorkspaceRole
from app.utils.security import hash_password


@pytest.mark.asyncio
async def test_create_classroom_requires_teacher_role(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
):
    user = User(
        email="viewer@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="Viewer Workspace")
    db_session.add_all([user, workspace])
    await db_session.flush()
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.VIEWER
    )
    db_session.add(membership)
    await db_session.commit()

    response = await client.post(
        "/api/classrooms/",
        json={"name": "Blocked Classroom"},
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert response.status_code == 403
    assert "Teacher privileges required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_students_in_classroom(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
):
    user = User(
        email="teacher@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="School Workspace")
    db_session.add_all([user, workspace])
    await db_session.flush()
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.TEACHER
    )
    classroom = Classroom(workspace_id=workspace.id, name="Math")
    db_session.add(classroom)
    await db_session.flush()
    student = Student(
        workspace_id=workspace.id,
        classroom_id=classroom.id,
        first_name="Sam",
        last_name="Student",
        display_name="Sam Student",
    )
    db_session.add_all([membership, student])
    await db_session.commit()

    response = await client.get(
        f"/api/classrooms/{classroom.id}/students",
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["first_name"] == "Sam"

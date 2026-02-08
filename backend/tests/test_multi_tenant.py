"""Tests for multi-tenancy and workspace access."""
import pytest
from tests.utils import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User, Workspace, WorkspaceMember
from app.models.enums import WorkspaceType, WorkspaceRole
from app.utils.security import hash_password


@pytest.mark.asyncio
async def test_workspace_isolation(client: AsyncClient, db_session: AsyncSession):
    """Test that workspaces are properly isolated."""
    # Create two users
    user1 = User(
        email="user1@example.com",
        hashed_password=hash_password("password"),
        is_active=True,
    )
    user2 = User(
        email="user2@example.com",
        hashed_password=hash_password("password"),
        is_active=True,
    )
    db_session.add_all([user1, user2])
    await db_session.flush()

    # Create two workspaces
    workspace1 = Workspace(name="Workspace 1", workspace_type=WorkspaceType.PERSONAL)
    workspace2 = Workspace(name="Workspace 2", workspace_type=WorkspaceType.PERSONAL)
    db_session.add_all([workspace1, workspace2])
    await db_session.flush()

    # Assign users to their workspaces
    member1 = WorkspaceMember(
        workspace_id=workspace1.id, user_id=user1.id, role=WorkspaceRole.OWNER
    )
    member2 = WorkspaceMember(
        workspace_id=workspace2.id, user_id=user2.id, role=WorkspaceRole.OWNER
    )
    db_session.add_all([member1, member2])
    await db_session.commit()

    # Login as user1
    response = await client.post(
        "/api/auth/login",
        json={"email": "user1@example.com", "password": "password"},
    )
    token1 = response.json()["access_token"]

    # Try to access workspace2 with user1's token (should fail)
    response = await client.get(
        "/api/workspaces/",
        headers={
            "Authorization": f"Bearer {token1}",
            "X-Workspace-Id": str(workspace2.id),
        },
    )

    # User1 should only see workspace1
    assert response.status_code == 200
    workspaces = response.json()
    assert len(workspaces) == 1
    assert workspaces[0]["id"] == str(workspace1.id)


@pytest.mark.asyncio
async def test_role_based_access(client: AsyncClient, db_session: AsyncSession):
    """Test role-based access control."""
    # Create user
    user = User(
        email="teacher@example.com",
        hashed_password=hash_password("password"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    # Create workspace
    workspace = Workspace(name="School", workspace_type=WorkspaceType.SCHOOL)
    db_session.add(workspace)
    await db_session.flush()

    # Assign as TEACHER (not OWNER)
    member = WorkspaceMember(
        workspace_id=workspace.id, user_id=user.id, role=WorkspaceRole.TEACHER
    )
    db_session.add(member)
    await db_session.commit()

    # Login
    response = await client.post(
        "/api/auth/login",
        json={"email": "teacher@example.com", "password": "password"},
    )
    token = response.json()["access_token"]

    # TEACHER should be able to create classrooms
    response = await client.post(
        "/api/classrooms/",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Workspace-Id": str(workspace.id),
        },
        json={"name": "Test Classroom"},
    )
    assert response.status_code == 201

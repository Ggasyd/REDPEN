"""Workspace access and validation tests."""
import pytest
from tests.utils import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, WorkspaceMember, WorkspaceSettings
from app.models.enums import WorkspaceRole, WorkspaceType
from app.utils.security import hash_password


@pytest.mark.asyncio
async def test_list_workspaces_requires_auth(client: AsyncClient):
    response = await client.get("/api/workspaces/")

    assert response.status_code in {401, 403}


@pytest.mark.asyncio
async def test_create_workspace_creates_settings(
    client: AsyncClient, db_session: AsyncSession, auth_headers
):
    user = User(
        email="owner@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.post(
        "/api/workspaces/",
        json={"name": "New School", "workspace_type": WorkspaceType.SCHOOL.value},
        headers=auth_headers(user),
    )

    assert response.status_code == 201

    result = await db_session.execute(select(WorkspaceSettings))
    settings = result.scalar_one()
    assert settings.retention_submissions_days is not None


@pytest.mark.asyncio
async def test_workspace_header_missing_returns_400(
    client: AsyncClient, db_session: AsyncSession, auth_headers
):
    user = User(
        email="teacher@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.post(
        "/api/exams/",
        json={"title": "Missing Header"},
        headers=auth_headers(user),
    )

    assert response.status_code == 400
    assert "X-Workspace-Id" in response.json()["detail"]


@pytest.mark.asyncio
async def test_workspace_header_invalid_returns_400(
    client: AsyncClient, db_session: AsyncSession, auth_headers
):
    user = User(
        email="invalid-header@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.post(
        "/api/exams/",
        json={"title": "Invalid Header"},
        headers={**auth_headers(user), "X-Workspace-Id": "not-a-uuid"},
    )

    assert response.status_code == 400
    assert "Invalid workspace ID format" in response.json()["detail"]


@pytest.mark.asyncio
async def test_workspace_access_denied_for_non_member(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
):
    user = User(
        email="outsider@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="Private Workspace")
    db_session.add_all([user, workspace])
    await db_session.commit()

    response = await client.post(
        "/api/exams/",
        json={"title": "Not Allowed"},
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]

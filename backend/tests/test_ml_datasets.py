"""ML datasets endpoint tests."""
import pytest
from tests.utils import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.models.enums import WorkspaceRole
from app.utils.security import hash_password


@pytest.mark.asyncio
async def test_export_datasets_requires_admin(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
):
    user = User(
        email="ml-admin@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="ML Workspace")
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.ADMIN
    )
    db_session.add_all([user, workspace, membership])
    await db_session.commit()

    response = await client.get(
        "/api/ml/datasets/supervised",
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert response.status_code == 200
    assert response.json()["count"] == 0


@pytest.mark.asyncio
async def test_calibration_metrics_empty(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
):
    user = User(
        email="ml-metrics@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="Metrics Workspace")
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.ADMIN
    )
    db_session.add_all([user, workspace, membership])
    await db_session.commit()

    response = await client.get(
        "/api/ml/calibration/metrics",
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "No calibration data yet"

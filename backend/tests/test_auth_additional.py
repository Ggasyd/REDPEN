"""Additional tests for authentication flows."""
from datetime import timedelta

import pytest
from tests.utils import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
)


@pytest.mark.asyncio
async def test_refresh_token_flow(client: AsyncClient, db_session: AsyncSession):
    user = User(
        email="refresh@example.com",
        hashed_password="hashed",
        full_name="Refresh User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    refresh_token = create_refresh_token({"sub": str(user.id)})
    response = await client.post(
        "/api/auth/refresh", json={"refresh_token": refresh_token}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    assert data["refresh_token"]
    decoded = decode_token(data["access_token"])
    assert decoded["sub"] == str(user.id)
    assert decoded["type"] == "access"


@pytest.mark.asyncio
async def test_refresh_rejects_access_token(client: AsyncClient, db_session: AsyncSession):
    user = User(
        email="access@example.com",
        hashed_password="hashed",
        full_name="Access User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    access_token = create_access_token({"sub": str(user.id)})
    response = await client.post(
        "/api/auth/refresh", json={"refresh_token": access_token}
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_requires_auth(client: AsyncClient):
    response = await client.post("/api/auth/logout")

    assert response.status_code in {401, 403}


@pytest.mark.asyncio
async def test_logout_success(
    client: AsyncClient, db_session: AsyncSession, auth_headers
):
    user = User(
        email="logout@example.com",
        hashed_password="hashed",
        full_name="Logout User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.post("/api/auth/logout", headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"


@pytest.mark.asyncio
async def test_inactive_user_login_denied(client: AsyncClient, db_session: AsyncSession):
    user = User(
        email="inactive@example.com",
        hashed_password=hash_password("password123"),
        full_name="Inactive User",
        is_active=False,
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.post(
        "/api/auth/login",
        json={"email": "inactive@example.com", "password": "password123"},
    )

    assert response.status_code == 403
    assert "inactive" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_invalid_registration_payloads(client: AsyncClient):
    response = await client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "password": "short"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_invalid_login_payload(client: AsyncClient):
    response = await client.post(
        "/api/auth/login",
        json={"email": "not-an-email", "password": "password123"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_expired_access_token_rejected(
    client: AsyncClient, db_session: AsyncSession
):
    user = User(
        email="expired@example.com",
        hashed_password="hashed",
        full_name="Expired User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    expired_token = create_access_token(
        {"sub": str(user.id)}, expires_delta=timedelta(seconds=-1)
    )

    response = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"}
    )

    assert response.status_code == 401

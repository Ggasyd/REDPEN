"""Security-related access tests."""
from uuid import uuid4

import pytest
from tests.utils import AsyncClient


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/api/classrooms/"),
        ("post", "/api/exams/"),
        ("get", "/api/gdpr/settings/retention"),
        ("get", "/api/ml/datasets/supervised"),
    ],
)
async def test_protected_endpoints_require_auth(client: AsyncClient, method, path):
    headers = {"X-Workspace-Id": str(uuid4())}
    response = await client.request(method, path, headers=headers, json={})

    assert response.status_code in {401, 403}

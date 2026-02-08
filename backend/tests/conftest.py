"""Test configuration and fixtures."""
import os
import asyncio
import importlib.util
from typing import AsyncGenerator, Callable

import pytest
from tests.utils import ASGITransport, AsyncClient

SQLALCHEMY_AVAILABLE = importlib.util.find_spec("sqlalchemy") is not None

if SQLALCHEMY_AVAILABLE:
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
else:
    AsyncSession = object  # type: ignore[assignment]
    async_sessionmaker = None
    create_async_engine = None

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
os.environ.setdefault("MINIO_ACCESS_KEY", "minio-access")
os.environ.setdefault("MINIO_SECRET_KEY", "minio-secret")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("GOOGLE_API_KEY", "test-google-key")
os.environ.setdefault("MISTRAL_API_KEY", "test-mistral-key")

if SQLALCHEMY_AVAILABLE:
    from app.database import Base, get_db
    from app.main import app
    from app.models import User, Workspace, WorkspaceMember
    from app.models.enums import WorkspaceRole, WorkspaceType
    from app.utils.security import create_access_token, hash_password
else:
    Base = None
    get_db = None
    app = None
    User = Workspace = WorkspaceMember = object  # type: ignore
    WorkspaceRole = WorkspaceType = object  # type: ignore
    create_access_token = hash_password = None

if SQLALCHEMY_AVAILABLE:
    def _build_test_database_url() -> str:
        database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
        if database_url.startswith("postgresql://"):
            return database_url.replace("postgresql://", "postgresql+asyncpg://")
        return database_url

    TEST_DATABASE_URL = _build_test_database_url()

    # Create test engine
    test_engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )

    TestSessionLocal = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


def pytest_collection_modifyitems(config, items):
    if SQLALCHEMY_AVAILABLE:
        return
    skip_marker = pytest.mark.skip(
        reason="sqlalchemy is required for backend tests"
    )
    for item in items:
        item.add_marker(skip_marker)


def pytest_ignore_collect(path, config):
    if not SQLALCHEMY_AVAILABLE and path.basename != "test_environment.py":
        return True
    return False


if SQLALCHEMY_AVAILABLE:

    @pytest.fixture(scope="function")
    async def db_session() -> AsyncGenerator[AsyncSession, None]:
        """Create a fresh database session for each test."""
        # Create tables
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Create session
        async with TestSessionLocal() as session:
            yield session

        # Drop tables
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


    @pytest.fixture(scope="function")
    async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
        """Create test client with overridden database."""

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

        app.dependency_overrides.clear()
else:

    @pytest.fixture(scope="function")
    async def db_session() -> AsyncGenerator[AsyncSession, None]:
        pytest.skip("sqlalchemy is required for backend tests")
        yield  # pragma: no cover


    @pytest.fixture(scope="function")
    async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
        pytest.skip("sqlalchemy is required for backend tests")
        yield  # pragma: no cover


@pytest.fixture()
def user_factory() -> Callable[..., User]:
    def _factory(
        *,
        email: str,
        password: str = "password123",
        full_name: str | None = None,
        is_active: bool = True,
        is_verified: bool = False,
    ) -> User:
        return User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            is_active=is_active,
            is_verified=is_verified,
        )

    return _factory


@pytest.fixture()
def workspace_factory() -> Callable[..., Workspace]:
    def _factory(
        *,
        name: str,
        workspace_type: WorkspaceType = WorkspaceType.SCHOOL,
        is_active: bool = True,
    ) -> Workspace:
        return Workspace(
            name=name,
            workspace_type=workspace_type,
            is_active=is_active,
        )

    return _factory


@pytest.fixture()
def membership_factory() -> Callable[..., WorkspaceMember]:
    def _factory(
        *,
        user_id,
        workspace_id,
        role: WorkspaceRole = WorkspaceRole.TEACHER,
    ) -> WorkspaceMember:
        return WorkspaceMember(
            user_id=user_id,
            workspace_id=workspace_id,
            role=role,
        )

    return _factory


@pytest.fixture()
def auth_headers() -> Callable[[User], dict[str, str]]:
    def _headers(user: User) -> dict[str, str]:
        token = create_access_token({"sub": str(user.id)})
        return {"Authorization": f"Bearer {token}"}

    return _headers


@pytest.fixture()
def workspace_headers() -> Callable[[Workspace], dict[str, str]]:
    def _headers(workspace: Workspace) -> dict[str, str]:
        return {"X-Workspace-Id": str(workspace.id)}

    return _headers

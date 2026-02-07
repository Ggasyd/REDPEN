"""FastAPI dependencies for authentication and multi-tenancy."""
from typing import Optional
from uuid import UUID
from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User, WorkspaceMember, WorkspaceRole
from app.utils.security import decode_token

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user from JWT token."""
    token = credentials.credentials
    payload = decode_token(token)

    if payload is None or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    # Fetch user from database
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


async def get_workspace_id(
    x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-Id"),
) -> UUID:
    """Extract workspace ID from header."""
    if not x_workspace_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Workspace-Id header is required",
        )

    try:
        return UUID(x_workspace_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace ID format",
        )


async def verify_workspace_access(
    current_user: User = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceMember:
    """Verify user has access to workspace and return membership."""
    result = await db.execute(
        select(WorkspaceMember)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .where(WorkspaceMember.user_id == current_user.id)
    )
    membership = result.scalar_one_or_none()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this workspace",
        )

    return membership


async def require_workspace_role(
    required_role: WorkspaceRole,
    membership: WorkspaceMember = Depends(verify_workspace_access),
) -> WorkspaceMember:
    """Verify user has required role in workspace."""
    role_hierarchy = {
        WorkspaceRole.VIEWER: 1,
        WorkspaceRole.TEACHER: 2,
        WorkspaceRole.ADMIN: 3,
        WorkspaceRole.OWNER: 4,
    }

    if role_hierarchy.get(membership.role, 0) < role_hierarchy.get(required_role, 99):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Required role: {required_role.value}",
        )

    return membership


def require_owner(
    membership: WorkspaceMember = Depends(verify_workspace_access),
) -> WorkspaceMember:
    """Require OWNER role."""
    if membership.role != WorkspaceRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace owners can perform this action",
        )
    return membership


def require_admin(
    membership: WorkspaceMember = Depends(verify_workspace_access),
) -> WorkspaceMember:
    """Require ADMIN or OWNER role."""
    if membership.role not in [WorkspaceRole.ADMIN, WorkspaceRole.OWNER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or owner privileges required",
        )
    return membership


def require_teacher(
    membership: WorkspaceMember = Depends(verify_workspace_access),
) -> WorkspaceMember:
    """Require TEACHER, ADMIN, or OWNER role."""
    if membership.role not in [
        WorkspaceRole.TEACHER,
        WorkspaceRole.ADMIN,
        WorkspaceRole.OWNER,
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teacher privileges required",
        )
    return membership

"""Workspaces routes."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.database import get_db
from app.models import User, Workspace, WorkspaceMember, WorkspaceSettings
from app.models.enums import WorkspaceRole
from app.schemas.workspace import WorkspaceCreate, WorkspaceResponse
from app.dependencies import get_current_user
from app.config import settings

router = APIRouter()


@router.get("/", response_model=List[WorkspaceResponse])
async def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all workspaces user belongs to."""
    result = await db.execute(
        select(Workspace)
        .join(WorkspaceMember)
        .where(WorkspaceMember.user_id == current_user.id)
        .where(Workspace.is_active)
    )
    workspaces = result.scalars().all()

    return [
        WorkspaceResponse(
            id=str(w.id),
            name=w.name,
            workspace_type=w.workspace_type,
            is_active=w.is_active,
            created_at=w.created_at,
        )
        for w in workspaces
    ]


@router.post("/", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    workspace_data: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new workspace (e.g., SCHOOL)."""
    # Create workspace
    workspace = Workspace(
        name=workspace_data.name,
        workspace_type=workspace_data.workspace_type,
        is_active=True,
    )
    db.add(workspace)
    await db.flush()

    # Add creator as OWNER
    membership = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=current_user.id,
        role=WorkspaceRole.OWNER,
    )
    db.add(membership)

    # Create default GDPR settings
    workspace_settings = WorkspaceSettings(
        workspace_id=workspace.id,
        retention_submissions_days=settings.default_retention_submissions_days,
        retention_artifacts_days=settings.default_retention_artifacts_days,
        retention_ml_days=settings.default_retention_ml_days,
    )
    db.add(workspace_settings)

    await db.commit()
    await db.refresh(workspace)

    return WorkspaceResponse(
        id=str(workspace.id),
        name=workspace.name,
        workspace_type=workspace.workspace_type,
        is_active=workspace.is_active,
        created_at=workspace.created_at,
    )

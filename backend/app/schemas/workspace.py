"""Workspace schemas."""
from pydantic import BaseModel, Field
from datetime import datetime
from app.models.enums import WorkspaceType, WorkspaceRole


class WorkspaceCreate(BaseModel):
    """Create workspace schema."""

    name: str = Field(..., min_length=1, max_length=255)
    workspace_type: WorkspaceType = WorkspaceType.PERSONAL


class WorkspaceResponse(BaseModel):
    """Workspace response schema."""

    id: str
    name: str
    workspace_type: WorkspaceType
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class WorkspaceMemberResponse(BaseModel):
    """Workspace member response."""

    id: str
    workspace_id: str
    user_id: str
    role: WorkspaceRole
    created_at: datetime

    class Config:
        from_attributes = True

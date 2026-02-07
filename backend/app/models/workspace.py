"""Workspace and WorkspaceMember models."""

from sqlalchemy import Column, String, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.models.base import BaseModel
from app.models.enums import WorkspaceType, WorkspaceRole


class Workspace(BaseModel):
    """Workspace model for multi-tenancy."""

    __tablename__ = "workspaces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    workspace_type = Column(
        SQLEnum(WorkspaceType, name="workspace_type"),
        nullable=False,
        default=WorkspaceType.PERSONAL,
    )
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    members = relationship(
        "WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan"
    )
    classrooms = relationship(
        "Classroom", back_populates="workspace", cascade="all, delete-orphan"
    )
    exams = relationship(
        "Exam", back_populates="workspace", cascade="all, delete-orphan"
    )
    settings = relationship(
        "WorkspaceSettings",
        back_populates="workspace",
        uselist=False,
        cascade="all, delete-orphan",
    )


class WorkspaceMember(BaseModel):
    """Workspace membership with roles."""

    __tablename__ = "workspace_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role = Column(
        SQLEnum(WorkspaceRole, name="workspace_role"),
        nullable=False,
        default=WorkspaceRole.VIEWER,
    )

    # Relationships
    workspace = relationship("Workspace", back_populates="members")
    user = relationship("User", back_populates="workspace_memberships")

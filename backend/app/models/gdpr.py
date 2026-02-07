"""GDPR and data retention models."""

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.models.base import GUID as UUID
from app.models.base import BaseModel, JSONType
from app.models.enums import RetentionMode


class WorkspaceSettings(BaseModel):
    """GDPR and retention settings for workspace."""

    __tablename__ = "workspace_settings"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Retention policies (in days)
    retention_submissions_days = Column(Integer, default=730, nullable=False)
    retention_artifacts_days = Column(Integer, default=365, nullable=False)
    retention_ml_days = Column(Integer, default=365, nullable=False)

    # GDPR options
    anonymize_on_expiry = Column(Boolean, default=True, nullable=False)
    hard_delete_on_expiry = Column(Boolean, default=False, nullable=False)
    ai_pseudonymize_before_send = Column(Boolean, default=True, nullable=False)
    eu_only_mode = Column(Boolean, default=False, nullable=False)

    # Relationships
    workspace = relationship("Workspace", back_populates="settings")


class DataRetentionRun(BaseModel):
    """GDPR retention enforcement runs."""

    __tablename__ = "data_retention_runs"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Run details
    mode = Column(
        SQLEnum(RetentionMode, name="retention_mode"),
        nullable=False,
    )
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)

    # Results
    summary_json = Column(
        JSONType, nullable=True
    )  # {affected_submissions, artifacts_deleted, etc.}
    error_log = Column(JSONType, nullable=True)

    # Relationships
    workspace = relationship("Workspace")

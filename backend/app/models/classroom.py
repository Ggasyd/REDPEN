"""Classroom model."""

import uuid

from sqlalchemy import Column, ForeignKey, String, Text
from app.models.base import GUID as UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Classroom(BaseModel):
    """Classroom model for grouping students."""

    __tablename__ = "classrooms"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    grade_level = Column(String(50), nullable=True)
    academic_year = Column(String(20), nullable=True)

    # Relationships
    workspace = relationship("Workspace", back_populates="classrooms")
    students = relationship(
        "Student", back_populates="classroom", cascade="all, delete-orphan"
    )

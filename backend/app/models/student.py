"""Student model."""

from sqlalchemy import Column, String, ForeignKey, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.models.base import BaseModel


class Student(BaseModel):
    """Student model."""

    __tablename__ = "students"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    classroom_id = Column(
        UUID(as_uuid=True),
        ForeignKey("classrooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)  # Can be anonymized
    student_number = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)

    # GDPR fields
    is_anonymized = Column(Boolean, default=False, nullable=False)
    anonymized_at = Column(DateTime, nullable=True)

    # Relationships
    workspace = relationship("Workspace")
    classroom = relationship("Classroom", back_populates="students")
    submissions = relationship(
        "Submission", back_populates="student", cascade="all, delete-orphan"
    )
    assignments = relationship(
        "StudentAssignment", back_populates="student", cascade="all, delete-orphan"
    )

"""Exam and related models."""

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from app.models.base import GUID as UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, JSONType
from app.models.enums import QuestionType


class Exam(BaseModel):
    """Exam model."""

    __tablename__ = "exams"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    subject = Column(String(255), nullable=True)
    grade_level = Column(String(50), nullable=True)
    total_points = Column(Float, nullable=True)

    # Relationships
    workspace = relationship("Workspace", back_populates="exams")
    versions = relationship(
        "ExamVersion", back_populates="exam", cascade="all, delete-orphan"
    )


class ExamVersion(BaseModel):
    """Exam version for iterating on exam definitions."""

    __tablename__ = "exam_versions"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    exam_id = Column(
        UUID(as_uuid=True),
        ForeignKey("exams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)

    # Relationships
    exam = relationship("Exam", back_populates="versions")
    rubric_document = relationship(
        "RubricDocument",
        back_populates="exam_version",
        uselist=False,
        cascade="all, delete-orphan",
    )
    questions = relationship(
        "Question", back_populates="exam_version", cascade="all, delete-orphan"
    )
    submissions = relationship(
        "Submission", back_populates="exam_version", cascade="all, delete-orphan"
    )


class RubricDocument(BaseModel):
    """Uploaded rubric/grading document."""

    __tablename__ = "rubric_documents"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    exam_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("exam_versions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    original_filename = Column(String(500), nullable=False)
    storage_url = Column(String(1000), nullable=False)
    extracted_text = Column(Text, nullable=True)
    metadata_json = Column(JSONType, nullable=True)

    # Relationships
    exam_version = relationship("ExamVersion", back_populates="rubric_document")


class Question(BaseModel):
    """Question definition with rubric criteria."""

    __tablename__ = "questions"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    exam_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("exam_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_number = Column(String(50), nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(
        SQLEnum(QuestionType, name="question_type"),
        nullable=False,
        default=QuestionType.OPEN,
    )
    max_points = Column(Float, nullable=False)
    order_index = Column(Integer, nullable=False)

    # For MCQ
    correct_answer = Column(String(10), nullable=True)  # e.g., "A", "B", "C"
    mcq_options = Column(JSONType, nullable=True)  # {"A": "text", "B": "text", ...}

    # Relationships
    exam_version = relationship("ExamVersion", back_populates="questions")
    rubric_criteria = relationship(
        "RubricCriterion", back_populates="question", cascade="all, delete-orphan"
    )
    answer_blocks = relationship(
        "AnswerBlock", back_populates="question", cascade="all, delete-orphan"
    )


class RubricCriterion(BaseModel):
    """Grading criteria for a question."""

    __tablename__ = "rubric_criteria"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    criterion_text = Column(Text, nullable=False)
    points = Column(Float, nullable=False)
    order_index = Column(Integer, nullable=False)

    # Relationships
    question = relationship("Question", back_populates="rubric_criteria")

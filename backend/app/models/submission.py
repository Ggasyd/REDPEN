"""Submission and related models."""
from sqlalchemy import Column, String, ForeignKey, Integer, Text, Float, Enum as SQLEnum, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from app.models.base import BaseModel
from app.models.enums import SubmissionStatus, BlockType, AssignMethod, StudentAssignMethod


class Submission(BaseModel):
    """Student submission (copy)."""

    __tablename__ = "submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    exam_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("exam_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    candidate_name = Column(String(500), nullable=True)  # Free-form name if no student_id

    # Processing
    status = Column(
        SQLEnum(SubmissionStatus, name="submission_status"),
        nullable=False,
        default=SubmissionStatus.UPLOADED,
    )
    original_filename = Column(String(500), nullable=False)
    storage_url = Column(String(1000), nullable=False)
    page_count = Column(Integer, nullable=True)

    # GDPR
    is_anonymized = Column(Boolean, default=False, nullable=False)
    anonymized_at = Column(DateTime, nullable=True)

    # Grading
    total_score = Column(Float, nullable=True)
    final_grade = Column(String(10), nullable=True)
    is_finalized = Column(Boolean, default=False, nullable=False)
    finalized_at = Column(DateTime, nullable=True)

    # Relationships
    workspace = relationship("Workspace")
    exam_version = relationship("ExamVersion", back_populates="submissions")
    student = relationship("Student", back_populates="submissions")
    pages = relationship(
        "SubmissionPage", back_populates="submission", cascade="all, delete-orphan"
    )
    student_assignment = relationship(
        "StudentAssignment",
        back_populates="submission",
        uselist=False,
        cascade="all, delete-orphan",
    )
    grade_decision = relationship(
        "GradeDecision",
        back_populates="submission",
        uselist=False,
        cascade="all, delete-orphan",
    )
    artifacts = relationship(
        "AnnotatedArtifact", back_populates="submission", cascade="all, delete-orphan"
    )


class SubmissionPage(BaseModel):
    """Individual page of a submission."""

    __tablename__ = "submission_pages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_number = Column(Integer, nullable=False)
    storage_url = Column(String(1000), nullable=False)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)

    # Relationships
    submission = relationship("Submission", back_populates="pages")
    answer_blocks = relationship(
        "AnswerBlock", back_populates="page", cascade="all, delete-orphan"
    )


class AnswerBlock(BaseModel):
    """Extracted answer block from a page."""

    __tablename__ = "answer_blocks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_id = Column(
        UUID(as_uuid=True),
        ForeignKey("submission_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Block identification
    block_type = Column(
        SQLEnum(BlockType, name="block_type"),
        nullable=False,
        default=BlockType.TEXT,
    )
    assign_method = Column(
        SQLEnum(AssignMethod, name="assign_method"),
        nullable=False,
    )

    # Geometry (bounding box)
    bbox_x = Column(Integer, nullable=False)
    bbox_y = Column(Integer, nullable=False)
    bbox_width = Column(Integer, nullable=False)
    bbox_height = Column(Integer, nullable=False)

    # Content
    transcription = Column(Text, nullable=True)  # Verbatim OCR/HTR
    crop_url = Column(String(1000), nullable=False)  # Image crop
    confidence = Column(Float, nullable=True)  # AI confidence

    # Flags
    is_ambiguous = Column(Boolean, default=False, nullable=False)
    is_illegible = Column(Boolean, default=False, nullable=False)
    needs_review = Column(Boolean, default=False, nullable=False)
    is_manually_edited = Column(Boolean, default=False, nullable=False)

    # Metadata
    metadata_json = Column(JSONB, nullable=True)  # Additional data from AI

    # Relationships
    page = relationship("SubmissionPage", back_populates="answer_blocks")
    question = relationship("Question", back_populates="answer_blocks")
    mcq_mark = relationship(
        "MCQMark",
        back_populates="answer_block",
        uselist=False,
        cascade="all, delete-orphan",
    )
    labels = relationship(
        "AnswerBlockLabel", back_populates="answer_block", cascade="all, delete-orphan"
    )


class StudentAssignment(BaseModel):
    """Student assignment to submission."""

    __tablename__ = "student_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Assignment logic
    assign_method = Column(
        SQLEnum(StudentAssignMethod, name="student_assign_method"),
        nullable=False,
    )
    ocr_candidate_name = Column(String(500), nullable=True)
    ai_suggested_name = Column(String(500), nullable=True)
    confidence = Column(Float, nullable=True)
    is_validated = Column(Boolean, default=False, nullable=False)

    # Relationships
    submission = relationship("Submission", back_populates="student_assignment")
    student = relationship("Student", back_populates="assignments")
    labels = relationship(
        "StudentAssignmentLabel",
        back_populates="assignment",
        cascade="all, delete-orphan",
    )


class MCQMark(BaseModel):
    """MCQ mark detection result."""

    __tablename__ = "mcq_marks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    answer_block_id = Column(
        UUID(as_uuid=True),
        ForeignKey("answer_blocks.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    detected_answer = Column(String(10), nullable=False)  # e.g., "A", "B"
    confidence = Column(Float, nullable=False)
    is_correct = Column(Boolean, nullable=True)

    # Relationships
    answer_block = relationship("AnswerBlock", back_populates="mcq_mark")


class GradeDecision(BaseModel):
    """Final grade decision for a submission."""

    __tablename__ = "grade_decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Grading details per question
    question_scores = Column(JSONB, nullable=True)  # {question_id: {score: X, max: Y}}
    total_score = Column(Float, nullable=False)
    max_score = Column(Float, nullable=False)
    percentage = Column(Float, nullable=True)
    letter_grade = Column(String(10), nullable=True)

    # AI suggestions
    ai_suggested_score = Column(Float, nullable=True)
    ai_justification = Column(Text, nullable=True)

    # Human decision
    final_score = Column(Float, nullable=False)
    teacher_notes = Column(Text, nullable=True)

    # Relationships
    submission = relationship("Submission", back_populates="grade_decision")
    feedback_comments = relationship(
        "FeedbackComment", back_populates="grade_decision", cascade="all, delete-orphan"
    )


class FeedbackComment(BaseModel):
    """Feedback comments on grade decisions."""

    __tablename__ = "feedback_comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grade_decision_id = Column(
        UUID(as_uuid=True),
        ForeignKey("grade_decisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="SET NULL"),
        nullable=True,
    )
    comment_text = Column(Text, nullable=False)
    is_ai_generated = Column(Boolean, default=False, nullable=False)

    # Relationships
    grade_decision = relationship("GradeDecision", back_populates="feedback_comments")
    question = relationship("Question")


class AnnotatedArtifact(BaseModel):
    """Generated artifacts (PDFs, images)."""

    __tablename__ = "annotated_artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_type = Column(String(50), nullable=False)
    storage_url = Column(String(1000), nullable=False)
    metadata = Column(JSONB, nullable=True)

    # Relationships
    submission = relationship("Submission", back_populates="artifacts")

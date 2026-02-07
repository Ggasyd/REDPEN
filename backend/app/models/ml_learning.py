"""Machine Learning and Human-in-the-Loop models."""
from sqlalchemy import Column, String, ForeignKey, Text, Float, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import JSONType
from sqlalchemy.orm import relationship
import uuid
from app.models.base import BaseModel
from app.models.enums import ActionEventType


class AnswerBlockLabel(BaseModel):
    """Supervised learning labels for answer blocks."""

    __tablename__ = "answer_block_labels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    answer_block_id = Column(
        UUID(as_uuid=True),
        ForeignKey("answer_blocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Original AI output
    original_transcription = Column(Text, nullable=True)
    original_question_id = Column(UUID(as_uuid=True), nullable=True)

    # Corrected by human
    corrected_transcription = Column(Text, nullable=True)
    corrected_question_id = Column(UUID(as_uuid=True), nullable=True)

    # Context
    correction_notes = Column(Text, nullable=True)

    # Relationships
    answer_block = relationship("AnswerBlock", back_populates="labels")
    workspace = relationship("Workspace")


class StudentAssignmentLabel(BaseModel):
    """Supervised learning labels for student assignments."""

    __tablename__ = "student_assignment_labels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assignment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("student_assignments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # AI suggestions
    ocr_candidate = Column(String(500), nullable=True)
    ai_candidate = Column(String(500), nullable=True)

    # Human decision
    assigned_student_id = Column(UUID(as_uuid=True), nullable=False)
    correction_notes = Column(Text, nullable=True)

    # Relationships
    assignment = relationship("StudentAssignment", back_populates="labels")
    workspace = relationship("Workspace")


class PreferenceSample(BaseModel):
    """Preference learning: AI output vs human decision."""

    __tablename__ = "preference_samples"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    submission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # AI output
    ai_output = Column(JSONType, nullable=False)  # {score, feedback, justification}

    # Human decision
    human_decision = Column(JSONType, nullable=False)  # {score, feedback, changes}

    # Preference (was AI accepted?)
    ai_accepted = Column(Boolean, nullable=False)
    modification_type = Column(String(100), nullable=True)

    # Relationships
    workspace = relationship("Workspace")
    submission = relationship("Submission")


class CalibrationRecord(BaseModel):
    """Calibration: AI confidence vs human acceptance."""

    __tablename__ = "calibration_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # AI prediction
    prediction_type = Column(String(100), nullable=False)  # transcription, assignment, grade
    ai_confidence = Column(Float, nullable=False)
    ai_output = Column(JSONType, nullable=False)

    # Human validation
    was_correct = Column(Boolean, nullable=False)
    human_feedback = Column(Text, nullable=True)

    # Context
    context_metadata = Column(JSONType, nullable=True)

    # Relationships
    workspace = relationship("Workspace")


class HumanActionEvent(BaseModel):
    """Audit log of human actions for ML learning."""

    __tablename__ = "human_action_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Event details
    event_type = Column(
        SQLEnum(ActionEventType, name="action_event_type"),
        nullable=False,
    )
    entity_type = Column(String(100), nullable=False)  # submission, answer_block, etc.
    entity_id = Column(UUID(as_uuid=True), nullable=False)

    # Before/After
    before_value = Column(JSONType, nullable=True)
    after_value = Column(JSONType, nullable=True)

    # Context
    action_metadata = Column(JSONType, nullable=True)

    # GDPR: can be sanitized
    is_sanitized = Column(Boolean, default=False, nullable=False)

    # Relationships
    workspace = relationship("Workspace")
    user = relationship("User")

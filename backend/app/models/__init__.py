"""Models package - imports all models for Alembic autogeneration."""
from app.models.base import Base, BaseModel, TimestampMixin
from app.models.enums import (
    WorkspaceType,
    WorkspaceRole,
    QuestionType,
    SubmissionStatus,
    BlockType,
    AssignMethod,
    StudentAssignMethod,
    ArtifactType,
    ActionEventType,
    RetentionMode,
)
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.models.classroom import Classroom
from app.models.student import Student
from app.models.exam import Exam, ExamVersion, RubricDocument, Question, RubricCriterion
from app.models.submission import (
    Submission,
    SubmissionPage,
    AnswerBlock,
    StudentAssignment,
    MCQMark,
    GradeDecision,
    FeedbackComment,
    AnnotatedArtifact,
)
from app.models.ml_learning import (
    AnswerBlockLabel,
    StudentAssignmentLabel,
    PreferenceSample,
    CalibrationRecord,
    HumanActionEvent,
)
from app.models.gdpr import WorkspaceSettings, DataRetentionRun

__all__ = [
    # Base
    "Base",
    "BaseModel",
    "TimestampMixin",
    # Enums
    "WorkspaceType",
    "WorkspaceRole",
    "QuestionType",
    "SubmissionStatus",
    "BlockType",
    "AssignMethod",
    "StudentAssignMethod",
    "ArtifactType",
    "ActionEventType",
    "RetentionMode",
    # Models
    "User",
    "Workspace",
    "WorkspaceMember",
    "Classroom",
    "Student",
    "Exam",
    "ExamVersion",
    "RubricDocument",
    "Question",
    "RubricCriterion",
    "Submission",
    "SubmissionPage",
    "AnswerBlock",
    "StudentAssignment",
    "MCQMark",
    "GradeDecision",
    "FeedbackComment",
    "AnnotatedArtifact",
    "AnswerBlockLabel",
    "StudentAssignmentLabel",
    "PreferenceSample",
    "CalibrationRecord",
    "HumanActionEvent",
    "WorkspaceSettings",
    "DataRetentionRun",
]

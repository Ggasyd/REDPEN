"""Models package - imports all models for Alembic autogeneration."""

from app.models.base import Base, BaseModel, TimestampMixin
from app.models.classroom import Classroom
from app.models.enums import (
    ActionEventType,
    ArtifactType,
    AssignMethod,
    BlockType,
    QuestionType,
    RetentionMode,
    StudentAssignMethod,
    SubmissionStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.models.exam import Exam, ExamVersion, Question, RubricCriterion, RubricDocument
from app.models.exam_template import ExamTemplate, TemplateZone
from app.models.gdpr import DataRetentionRun, WorkspaceSettings
from app.models.ml_learning import (
    AnswerBlockLabel,
    CalibrationRecord,
    HumanActionEvent,
    PreferenceSample,
    StudentAssignmentLabel,
)
from app.models.student import Student
from app.models.submission import (
    AnnotatedArtifact,
    AnswerBlock,
    FeedbackComment,
    GradeDecision,
    MCQMark,
    StudentAssignment,
    Submission,
    SubmissionPage,
)
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember

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
    "ExamTemplate",
    "TemplateZone",
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

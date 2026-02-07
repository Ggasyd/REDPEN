"""Enums for the application."""

import enum


class WorkspaceType(str, enum.Enum):
    """Workspace types."""

    PERSONAL = "PERSONAL"
    SCHOOL = "SCHOOL"


class WorkspaceRole(str, enum.Enum):
    """Workspace member roles."""

    OWNER = "OWNER"
    ADMIN = "ADMIN"
    TEACHER = "TEACHER"
    VIEWER = "VIEWER"


class QuestionType(str, enum.Enum):
    """Question types."""

    OPEN = "OPEN"
    MCQ = "MCQ"
    TABLE = "TABLE"
    MIXED = "MIXED"


class SubmissionStatus(str, enum.Enum):
    """Submission processing status."""

    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    REVIEWED = "REVIEWED"
    FINALIZED = "FINALIZED"
    ERROR = "ERROR"


class BlockType(str, enum.Enum):
    """Answer block types."""

    TEXT = "TEXT"
    MCQ = "MCQ"
    TABLE = "TABLE"
    DRAWING = "DRAWING"
    MIXED = "MIXED"


class AssignMethod(str, enum.Enum):
    """Answer block assignment method."""

    GEOMETRIC = "GEOMETRIC"
    SEMANTIC = "SEMANTIC"
    DETECTION = "DETECTION"
    MANUAL = "MANUAL"


class StudentAssignMethod(str, enum.Enum):
    """Student assignment method."""

    EXPLICIT = "EXPLICIT"
    OCR_AUTO = "OCR_AUTO"
    AI_SUGGESTED = "AI_SUGGESTED"
    MANUAL = "MANUAL"


class ArtifactType(str, enum.Enum):
    """Artifact types."""

    SUBJECT_PDF = "SUBJECT_PDF"
    RUBRIC_PDF = "RUBRIC_PDF"
    SUBMISSION_PDF = "SUBMISSION_PDF"
    PAGE_IMAGE = "PAGE_IMAGE"
    ANSWER_CROP = "ANSWER_CROP"
    ANNOTATED_PDF = "ANNOTATED_PDF"


class ActionEventType(str, enum.Enum):
    """Human action event types for ML learning."""

    TRANSCRIPTION_CORRECTED = "TRANSCRIPTION_CORRECTED"
    QUESTION_REASSIGNED = "QUESTION_REASSIGNED"
    STUDENT_ASSIGNED = "STUDENT_ASSIGNED"
    GRADE_MODIFIED = "GRADE_MODIFIED"
    FEEDBACK_ADDED = "FEEDBACK_ADDED"
    BLOCK_FLAGGED = "BLOCK_FLAGGED"
    BLOCK_APPROVED = "BLOCK_APPROVED"


class RetentionMode(str, enum.Enum):
    """GDPR retention run modes."""

    PREVIEW = "PREVIEW"
    ANONYMIZE = "ANONYMIZE"
    DELETE = "DELETE"

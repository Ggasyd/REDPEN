"""Exam template models for OCR zone extraction."""

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.models.base import GUID as UUID
from app.models.base import BaseModel, JSONType


class ExamTemplate(BaseModel):
    """Template PDF and derived metadata for an exam version."""

    __tablename__ = "exam_templates"
    __table_args__ = (
        UniqueConstraint(
            "exam_version_id",
            "template_hash",
            name="uq_exam_templates_hash_per_version",
        ),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    exam_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("exam_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_hash = Column(String(128), nullable=False)
    original_filename = Column(String(500), nullable=False)
    storage_url = Column(String(1000), nullable=False)
    content_type = Column(String(100), nullable=False, default="application/pdf")
    file_size = Column(Integer, nullable=False)
    page_count = Column(Integer, nullable=False)
    dpi = Column(Integer, nullable=False, default=250)
    metadata_json = Column(JSONType, nullable=True)

    exam_version = relationship(
        "ExamVersion",
        back_populates="templates",
        foreign_keys=[exam_version_id],
    )
    zones = relationship(
        "TemplateZone", back_populates="template", cascade="all, delete-orphan"
    )


class TemplateZone(BaseModel):
    """Template zone mapping to a question."""

    __tablename__ = "template_zones"
    __table_args__ = (Index("ix_template_zones_question_key", "question_key"),)

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("exam_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_index = Column(Integer, nullable=False)
    question_key = Column(String(50), nullable=False)
    bbox_x = Column(Integer, nullable=False)
    bbox_y = Column(Integer, nullable=False)
    bbox_width = Column(Integer, nullable=False)
    bbox_height = Column(Integer, nullable=False)
    pad_ratio = Column(Float, nullable=False, default=0.10)
    confidence = Column(Float, nullable=True)
    source = Column(String(20), nullable=False, default="vector")
    is_validated = Column(Boolean, nullable=False, default=False)
    validated_at = Column(DateTime, nullable=True)
    validated_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_edited_at = Column(DateTime, nullable=True)
    last_edited_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    edit_source = Column(String(20), nullable=False, default="auto")

    template = relationship("ExamTemplate", back_populates="zones")
    revisions = relationship(
        "TemplateZoneRevision", back_populates="zone", cascade="all, delete-orphan"
    )


class TemplateZoneRevision(BaseModel):
    """Immutable revision log for template zone changes."""

    __tablename__ = "template_zone_revisions"
    __table_args__ = (
        Index("ix_template_zone_revisions_zone_rev", "zone_id", "revision_number"),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    zone_id = Column(
        UUID(as_uuid=True),
        ForeignKey("template_zones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("exam_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision_number = Column(Integer, nullable=False)
    change_type = Column(String(30), nullable=False)
    change_reason = Column(String(255), nullable=True)
    changed_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    changed_at = Column(DateTime, nullable=False)

    page_index = Column(Integer, nullable=False)
    question_key = Column(String(50), nullable=False)
    bbox_x = Column(Integer, nullable=False)
    bbox_y = Column(Integer, nullable=False)
    bbox_width = Column(Integer, nullable=False)
    bbox_height = Column(Integer, nullable=False)
    pad_ratio = Column(Float, nullable=False, default=0.10)
    confidence = Column(Float, nullable=True)
    source = Column(String(20), nullable=False)
    is_validated = Column(Boolean, nullable=False, default=False)
    edit_source = Column(String(20), nullable=False, default="auto")

    zone = relationship("TemplateZone", back_populates="revisions")

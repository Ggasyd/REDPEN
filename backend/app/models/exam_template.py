"""Exam template models for OCR zone extraction."""

import uuid

from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import GUID as UUID
from app.models.base import BaseModel, JSONType


class ExamTemplate(BaseModel):
    """Template PDF and derived metadata for an exam version."""

    __tablename__ = "exam_templates"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    exam_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("exam_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_hash = Column(String(128), nullable=False)
    page_count = Column(Integer, nullable=False)
    dpi = Column(Integer, nullable=False, default=250)
    metadata_json = Column(JSONType, nullable=True)

    exam_version = relationship("ExamVersion", foreign_keys=[exam_version_id])
    zones = relationship(
        "TemplateZone", back_populates="template", cascade="all, delete-orphan"
    )


class TemplateZone(BaseModel):
    """Template zone mapping to a question."""

    __tablename__ = "template_zones"

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

    template = relationship("ExamTemplate", back_populates="zones")

"""Base model with common fields."""

from datetime import datetime
from sqlalchemy import Column, DateTime, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declared_attr
from app.database import Base

# JSON type that works with both PostgreSQL and SQLite
# Use JSONB for PostgreSQL and JSON for SQLite
JSONType = JSON().with_variant(JSONB(), "postgresql")


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class BaseModel(Base, TimestampMixin):
    """Abstract base model with timestamps."""

    __abstract__ = True

    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower()

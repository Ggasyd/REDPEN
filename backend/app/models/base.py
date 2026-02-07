"""Base model with common fields."""

from datetime import datetime
from uuid import UUID as PyUUID

from sqlalchemy import JSON, Column, DateTime, String, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.declarative import declared_attr

from app.database import Base


# UUID type that works with both PostgreSQL and SQLite
class GUID(TypeDecorator):
    """Platform-independent GUID type.

    Uses PostgreSQL's UUID type, otherwise uses CHAR(36).
    """
    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value) if isinstance(value, PyUUID) else value
        else:
            return str(value) if isinstance(value, PyUUID) else value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, PyUUID):
                value = PyUUID(value)
            return value


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

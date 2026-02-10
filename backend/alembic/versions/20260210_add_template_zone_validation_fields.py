"""add template zone validation and editing fields

Revision ID: 20260210_template_zone_validation
Revises: 20260210_template_file_metadata
Create Date: 2026-02-10 00:30:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260210_template_zone_validation"
down_revision = "20260210_template_file_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "template_zones",
        sa.Column("is_validated", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("template_zones", sa.Column("validated_at", sa.DateTime(), nullable=True))
    op.add_column(
        "template_zones",
        sa.Column("validated_by", sa.String(length=36), nullable=True),
    )
    op.add_column("template_zones", sa.Column("last_edited_at", sa.DateTime(), nullable=True))
    op.add_column(
        "template_zones",
        sa.Column("last_edited_by", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "template_zones",
        sa.Column("edit_source", sa.String(length=20), nullable=False, server_default="auto"),
    )


def downgrade() -> None:
    op.drop_column("template_zones", "edit_source")
    op.drop_column("template_zones", "last_edited_by")
    op.drop_column("template_zones", "last_edited_at")
    op.drop_column("template_zones", "validated_by")
    op.drop_column("template_zones", "validated_at")
    op.drop_column("template_zones", "is_validated")

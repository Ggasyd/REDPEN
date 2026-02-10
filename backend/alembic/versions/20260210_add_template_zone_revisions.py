"""add template zone revisions table

Revision ID: 20260210_template_zone_revisions
Revises: 20260210_template_zone_validation
Create Date: 2026-02-10 01:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260210_template_zone_revisions"
down_revision = "20260210_template_zone_validation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "template_zone_revisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("zone_id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("change_type", sa.String(length=30), nullable=False),
        sa.Column("change_reason", sa.String(length=255), nullable=True),
        sa.Column("changed_by", sa.String(length=36), nullable=True),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
        sa.Column("page_index", sa.Integer(), nullable=False),
        sa.Column("question_key", sa.String(length=50), nullable=False),
        sa.Column("bbox_x", sa.Integer(), nullable=False),
        sa.Column("bbox_y", sa.Integer(), nullable=False),
        sa.Column("bbox_width", sa.Integer(), nullable=False),
        sa.Column("bbox_height", sa.Integer(), nullable=False),
        sa.Column("pad_ratio", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("is_validated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("edit_source", sa.String(length=20), nullable=False, server_default="auto"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["template_id"], ["exam_templates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["zone_id"], ["template_zones.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_template_zone_revisions_zone_rev",
        "template_zone_revisions",
        ["zone_id", "revision_number"],
    )
    op.create_index(
        "ix_template_zone_revisions_zone_id",
        "template_zone_revisions",
        ["zone_id"],
    )
    op.create_index(
        "ix_template_zone_revisions_template_id",
        "template_zone_revisions",
        ["template_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_template_zone_revisions_template_id", table_name="template_zone_revisions")
    op.drop_index("ix_template_zone_revisions_zone_id", table_name="template_zone_revisions")
    op.drop_index("ix_template_zone_revisions_zone_rev", table_name="template_zone_revisions")
    op.drop_table("template_zone_revisions")

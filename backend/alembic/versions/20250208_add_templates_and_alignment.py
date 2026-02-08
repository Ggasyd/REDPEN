"""add templates and alignment metadata

Revision ID: 20250208_add_templates
Revises: 
Create Date: 2025-02-08 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20250208_add_templates"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exam_templates",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "exam_version_id",
            sa.Uuid(),
            sa.ForeignKey("exam_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("template_hash", sa.String(length=128), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("dpi", sa.Integer(), nullable=False, server_default="250"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_exam_templates_exam_version_id",
        "exam_templates",
        ["exam_version_id"],
    )
    op.create_index(
        "uq_exam_templates_hash_per_version",
        "exam_templates",
        ["exam_version_id", "template_hash"],
        unique=True,
    )

    op.create_table(
        "template_zones",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "template_id",
            sa.Uuid(),
            sa.ForeignKey("exam_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page_index", sa.Integer(), nullable=False),
        sa.Column("question_key", sa.String(length=50), nullable=False),
        sa.Column("bbox_x", sa.Integer(), nullable=False),
        sa.Column("bbox_y", sa.Integer(), nullable=False),
        sa.Column("bbox_width", sa.Integer(), nullable=False),
        sa.Column("bbox_height", sa.Integer(), nullable=False),
        sa.Column(
            "pad_ratio", sa.Float(), nullable=False, server_default="0.10"
        ),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "source", sa.String(length=20), nullable=False, server_default="vector"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_template_zones_template_id",
        "template_zones",
        ["template_id"],
    )
    op.create_index(
        "ix_template_zones_question_key",
        "template_zones",
        ["question_key"],
    )

    op.add_column(
        "exam_versions",
        sa.Column(
            "active_template_id",
            sa.Uuid(),
            sa.ForeignKey("exam_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_exam_versions_active_template_id",
        "exam_versions",
        ["active_template_id"],
    )

    op.add_column("submissions", sa.Column("alignment_score", sa.Float(), nullable=True))
    op.add_column(
        "submissions", sa.Column("alignment_method", sa.String(length=30), nullable=True)
    )
    op.add_column(
        "submissions",
        sa.Column("alignment_rotation", sa.Integer(), nullable=True),
    )

    op.add_column(
        "answer_blocks",
        sa.Column("question_key", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("answer_blocks", "question_key")
    op.drop_column("submissions", "alignment_rotation")
    op.drop_column("submissions", "alignment_method")
    op.drop_column("submissions", "alignment_score")
    op.drop_index("ix_exam_versions_active_template_id", table_name="exam_versions")
    op.drop_column("exam_versions", "active_template_id")
    op.drop_index("ix_template_zones_question_key", table_name="template_zones")
    op.drop_index("ix_template_zones_template_id", table_name="template_zones")
    op.drop_table("template_zones")
    op.drop_index("uq_exam_templates_hash_per_version", table_name="exam_templates")
    op.drop_index("ix_exam_templates_exam_version_id", table_name="exam_templates")
    op.drop_table("exam_templates")

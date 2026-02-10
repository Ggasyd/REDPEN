"""add template file metadata fields

Revision ID: 20260210_template_file_metadata
Revises: 20250208_add_templates
Create Date: 2026-02-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260210_template_file_metadata"
down_revision = "20250208_add_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "exam_templates",
        sa.Column("original_filename", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "exam_templates",
        sa.Column("storage_url", sa.String(length=1000), nullable=True),
    )
    op.add_column(
        "exam_templates",
        sa.Column(
            "content_type",
            sa.String(length=100),
            nullable=False,
            server_default="application/pdf",
        ),
    )
    op.add_column(
        "exam_templates", sa.Column("file_size", sa.Integer(), nullable=True)
    )

    op.execute(
        "UPDATE exam_templates SET original_filename = 'template.pdf' "
        "WHERE original_filename IS NULL"
    )
    op.execute(
        "UPDATE exam_templates SET storage_url = '' WHERE storage_url IS NULL"
    )
    op.execute("UPDATE exam_templates SET file_size = 0 WHERE file_size IS NULL")

    op.alter_column("exam_templates", "original_filename", nullable=False)
    op.alter_column("exam_templates", "storage_url", nullable=False)
    op.alter_column("exam_templates", "file_size", nullable=False)


def downgrade() -> None:
    op.drop_column("exam_templates", "file_size")
    op.drop_column("exam_templates", "content_type")
    op.drop_column("exam_templates", "storage_url")
    op.drop_column("exam_templates", "original_filename")

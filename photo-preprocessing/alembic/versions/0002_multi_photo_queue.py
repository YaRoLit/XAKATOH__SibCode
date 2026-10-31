"""multi-photo processing_queue

Revision ID: 0002_multi_photo
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_multi_photo"
down_revision = "0001"


def upgrade() -> None:
    op.add_column("processing_queue", sa.Column("survey_ids", postgresql.JSONB(), nullable=True))
    op.add_column("processing_queue", sa.Column("primary_survey_id", sa.Integer(), nullable=True))
    op.add_column("processing_queue", sa.Column("batch_id", sa.String(64), nullable=True))
    op.add_column("processing_queue", sa.Column("capture_date", sa.Date(), nullable=True))
    op.create_index("ix_queue_batch_id", "processing_queue", ["batch_id"])
    op.execute(
        """
        UPDATE processing_queue q
        SET
            survey_ids = COALESCE(q.survey_ids, jsonb_build_array(q.survey_id)),
            primary_survey_id = COALESCE(q.primary_survey_id, q.survey_id),
            batch_id = COALESCE(q.batch_id, s.batch_id)
        FROM surveys s
        WHERE s.id = q.survey_id
        """
    )
    op.drop_constraint("processing_queue_survey_id_key", "processing_queue", type_="unique")
    op.drop_constraint("processing_queue_survey_id_fkey", "processing_queue", type_="foreignkey")
    op.alter_column("processing_queue", "survey_id", nullable=True)
    op.create_unique_constraint("uq_queue_batch_object", "processing_queue", ["batch_id", "object_id"])


def downgrade() -> None:
    op.drop_constraint("uq_queue_batch_object", "processing_queue", type_="unique")
    op.drop_index("ix_queue_batch_id", table_name="processing_queue")
    op.drop_column("processing_queue", "capture_date")
    op.drop_column("processing_queue", "batch_id")
    op.drop_column("processing_queue", "primary_survey_id")
    op.drop_column("processing_queue", "survey_ids")

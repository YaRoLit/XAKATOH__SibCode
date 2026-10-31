"""initial schema + seed object

Revision ID: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None


def upgrade() -> None:
    # 1. Создаем таблицы
    op.create_table(
        "objects",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("cadastral_number", sa.String(64), unique=True),
        sa.Column("address", sa.Text()),
        sa.Column("plot_corners", sa.JSON()),
        sa.Column("status", sa.String(32), default="active"),
    )
    
    op.create_table(
        "batches",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("operator_id", sa.String(64)),
        sa.Column("status", sa.String(32), default="uploading"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    op.create_table(
        "surveys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.String(64), sa.ForeignKey("batches.id")),
        sa.Column("filename", sa.String(255)),
        sa.Column("file_hash", sa.String(64)),
        sa.Column("status", sa.String(32), default="pending"),
        sa.Column("metadata", sa.JSON()),
        sa.Column("validation_errors", sa.JSON()),
        sa.Column("object_id", sa.String(64), sa.ForeignKey("objects.id")),
        sa.Column("coverage", sa.Float()),
        sa.Column("duplicate_of", sa.Integer(), sa.ForeignKey("surveys.id")),
        sa.Column("temp_path", sa.Text()),
        sa.Column("preview_path", sa.Text()),
        sa.Column("s3_key", sa.Text()),
        sa.Column("preview_key", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    
    op.create_index("ix_surveys_batch", "surveys", ["batch_id"])
    op.create_index("ix_surveys_status", "surveys", ["status"])
    op.create_index("ix_surveys_hash", "surveys", ["file_hash"])
    
    op.create_table(
        "processing_queue",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("survey_id", sa.Integer(), sa.ForeignKey("surveys.id"), unique=True),
        sa.Column("object_id", sa.String(64), sa.ForeignKey("objects.id")),
        sa.Column("priority", sa.String(16), default="normal"),
        sa.Column("status", sa.String(32), default="pending"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("picked_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
    )
    op.create_index("ix_queue_status", "processing_queue", ["status"])

    # 2. Вставляем тестовый объект через bulk_insert (безопасно для двоеточий и JSON)
    objects_table = sa.table(
        'objects',
        sa.column('id', sa.String),
        sa.column('cadastral_number', sa.String),
        sa.column('address', sa.String),
        sa.column('plot_corners', sa.JSON),
        sa.column('status', sa.String)
    )

    op.bulk_insert(
        objects_table,
        [
            {
                'id': 'obj_123',
                'cadastral_number': '54:35:000000:123',
                'address': 'Новосибирская обл., тестовый участок',
                'plot_corners': [
                    {"lat": 54.7442888, "lon": 83.0844121},
                    {"lat": 54.7443778, "lon": 83.0844905},
                    {"lat": 54.7443348, "lon": 83.0846386},
                    {"lat": 54.7442464, "lon": 83.0845627}
                ],
                'status': 'active'
            },
            {
                'id': 'obj_124',
                'cadastral_number': '54:35:000000:124',
                'address': 'Новосибирская обл., соседний участок',
                'plot_corners': [
                    {"lat": 54.7450000, "lon": 83.0850000},
                    {"lat": 54.7451000, "lon": 83.0851000},
                    {"lat": 54.7450500, "lon": 83.0852000},
                    {"lat": 54.7449500, "lon": 83.0851000}
                ],
                'status': 'active'
            }
        ]
    )


def downgrade() -> None:
    op.drop_table("processing_queue")
    op.drop_table("surveys")
    op.drop_table("batches")
    op.drop_table("objects")
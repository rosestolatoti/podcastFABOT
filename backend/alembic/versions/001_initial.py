"""Initial migration

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'jobs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='PENDING'),
        sa.Column('progress', sa.Integer(), default=0),
        sa.Column('current_step', sa.String(255), default='Aguardando...'),
        sa.Column('script_json', sa.Text(), nullable=True),
        sa.Column('script_edited', sa.Boolean(), default=False),
        sa.Column('audio_path', sa.String(500), nullable=True),
        sa.Column('script_path', sa.String(500), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('llm_mode', sa.String(20), default='groq'),
        sa.Column('voice_host', sa.String(50)),
        sa.Column('voice_cohost', sa.String(50), nullable=True),
        sa.Column('podcast_type', sa.String(20), default='monologue'),
        sa.Column('target_duration', sa.Integer(), default=10),
        sa.Column('depth_level', sa.String(20), default='normal'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    
    op.create_table(
        'files',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('job_id', sa.String(36), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('original_name', sa.String(255), nullable=False),
        sa.Column('file_type', sa.String(20), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('char_count', sa.Integer(), default=0),
        sa.Column('status', sa.String(20), default='pending'),
    )


def downgrade() -> None:
    op.drop_table('files')
    op.drop_table('jobs')

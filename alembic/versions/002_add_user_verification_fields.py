"""Add email verification fields to users

Revision ID: 002
Revises: 001
Create Date: 2026-08-10

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('is_verified', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('users', sa.Column('verification_sent_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('verification_reminder_sent_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_attempts')
    op.drop_column('users', 'verification_reminder_sent_at')
    op.drop_column('users', 'verification_sent_at')
    op.drop_column('users', 'is_verified')

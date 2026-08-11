"""Fix now() server_default to work on SQLite (dialect-agnostic)

Revision ID: 003
Revises: 002
Create Date: 2026-08-11

Postgres already renders sa.text('now()') correctly, so production needs no
change — this migration is a no-op there. SQLite has no now() function, so
this switches its server_default to CURRENT_TIMESTAMP via sa.func.now(),
fixing local SQLite-backed testing/dev only.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None

# (table, column, existing_nullable)
_COLUMNS = [
    ('facilities', 'created_at', True),
    ('users', 'created_at', True),
    ('residents', 'created_at', True),
    ('assessments', 'created_at', True),
    ('audit_logs', 'timestamp', False),
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'sqlite':
        return

    for table, column, existing_nullable in _COLUMNS:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                column,
                existing_type=sa.DateTime(timezone=True),
                existing_nullable=existing_nullable,
                server_default=sa.func.now(),
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'sqlite':
        return

    for table, column, existing_nullable in _COLUMNS:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                column,
                existing_type=sa.DateTime(timezone=True),
                existing_nullable=existing_nullable,
                server_default=sa.text('now()'),
            )

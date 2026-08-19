"""Add subscription billing fields to facilities

Revision ID: 003
Revises: 002
Create Date: 2026-08-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # op.add_column() does not emit CREATE TYPE for enum columns the way
    # op.create_table() does (that only happens via the create-table DDL
    # event) — the type must be created explicitly first, guarded for
    # idempotency since some databases already have it from an out-of-band
    # create_all() race.
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute(
            "DO $$ BEGIN "
            "CREATE TYPE subscriptionstatus AS ENUM ('pending_payment', 'active', 'suspended'); "
            "EXCEPTION WHEN duplicate_object THEN null; "
            "END $$;"
        )

    op.add_column(
        'facilities',
        sa.Column(
            'subscription_status',
            postgresql.ENUM(
                'pending_payment', 'active', 'suspended', name='subscriptionstatus', create_type=False
            ),
            nullable=False,
            server_default='pending_payment',
        ),
    )
    op.add_column('facilities', sa.Column('stripe_customer_id', sa.String(length=255), nullable=True))
    op.add_column('facilities', sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('facilities', 'stripe_subscription_id')
    op.drop_column('facilities', 'stripe_customer_id')
    op.drop_column('facilities', 'subscription_status')
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("DROP TYPE IF EXISTS subscriptionstatus;")

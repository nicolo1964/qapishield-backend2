"""Move subscription details off Facility into subscription_plans/subscriptions

Revision ID: 004
Revises: 003
Create Date: 2026-08-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None

# Generic sa.Enum(..., create_type=False) doesn't reliably suppress CREATE
# TYPE inside op.create_table() — the Postgres-specific ENUM class does.
subscription_status_enum = postgresql.ENUM(
    'pending_payment', 'active', 'suspended', name='subscriptionstatus', create_type=False
)


def upgrade() -> None:
    op.drop_column('facilities', 'subscription_status')
    op.drop_column('facilities', 'stripe_subscription_id')

    # Defensive: app startup runs Base.metadata.create_all(), which can create
    # these tables directly from the models before this migration ever runs.
    # Drop them first (if present) so this migration is the single source of truth.
    op.execute('DROP TABLE IF EXISTS subscriptions CASCADE')
    op.execute('DROP TABLE IF EXISTS subscription_plans CASCADE')

    op.create_table(
        'subscription_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stripe_product_id', sa.String(length=255), nullable=False),
        sa.Column('stripe_price_id', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False),
        sa.Column('interval', sa.String(length=20), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stripe_price_id'),
    )
    op.create_index(op.f('ix_subscription_plans_id'), 'subscription_plans', ['id'], unique=False)

    op.create_table(
        'subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('facility_id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True),
        sa.Column(
            'status',
            subscription_status_enum,
            nullable=False,
            server_default='pending_payment',
        ),
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['facility_id'], ['facilities.id'], ),
        sa.ForeignKeyConstraint(['plan_id'], ['subscription_plans.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('facility_id'),
    )
    op.create_index(op.f('ix_subscriptions_id'), 'subscriptions', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_subscriptions_id'), table_name='subscriptions')
    op.drop_table('subscriptions')
    op.drop_index(op.f('ix_subscription_plans_id'), table_name='subscription_plans')
    op.drop_table('subscription_plans')

    op.add_column('facilities', sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True))
    op.add_column(
        'facilities',
        sa.Column(
            'subscription_status',
            subscription_status_enum,
            nullable=False,
            server_default='pending_payment',
        ),
    )

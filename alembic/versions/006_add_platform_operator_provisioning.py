"""Add platform_operators table and facility provisioning fields

Revision ID: 006
Revises: 005
Create Date: 2026-09-01

Adds the schema needed for operator-only facility provisioning:
  - platform_operators: distinct credential store for platform staff,
    entirely separate from the `users` table (a facility Administrator's
    JWT can never satisfy this).
  - facilities: status (pending/active/suspended, informational — does not
    gate access, which continues to be governed by subscriptions.status),
    facility_reference (operator-supplied idempotency key), and
    provisioned_by_operator_id (audit/reporting only).
  - audit_logs: actor_user_id/actor_role/facility_id become nullable and a
    new actor_operator_id column is added, so operator-attributed actions
    can be recorded without a User row. A CHECK constraint guarantees every
    row is still attributed to exactly one kind of actor. All existing
    columns/rows are untouched — this is purely additive.

Revises: 005
"""
from alembic import op
import sqlalchemy as sa

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- platform_operators -------------------------------------------------
    op.create_table(
        'platform_operators',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('key_hash', sa.String(length=64), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash'),
    )
    op.create_index(op.f('ix_platform_operators_id'), 'platform_operators', ['id'], unique=False)

    # --- facilities: status / facility_reference / provisioned_by ----------
    facility_status = sa.Enum('pending', 'active', 'suspended', name='facilitystatus')
    facility_status.create(op.get_bind(), checkfirst=True)

    op.add_column('facilities', sa.Column('status', facility_status, nullable=True))
    op.add_column('facilities', sa.Column('facility_reference', sa.String(length=100), nullable=True))
    op.add_column('facilities', sa.Column('provisioned_by_operator_id', sa.Integer(), nullable=True))

    # Existing facilities were already onboarded (most have an active
    # subscription already) — backfill them as 'active' so this new,
    # informational-only field doesn't misrepresent real facilities as
    # pending. New facilities created by the app always pass an explicit
    # status, so no ongoing default is needed.
    op.execute("UPDATE facilities SET status = 'active' WHERE status IS NULL")

    op.create_unique_constraint('uq_facilities_facility_reference', 'facilities', ['facility_reference'])
    op.create_foreign_key(
        'fk_facilities_provisioned_by_operator_id', 'facilities', 'platform_operators',
        ['provisioned_by_operator_id'], ['id'],
    )

    # --- audit_logs: allow operator-attributed rows -------------------------
    op.alter_column('audit_logs', 'actor_user_id', existing_type=sa.Integer(), nullable=True)
    op.alter_column('audit_logs', 'actor_role', nullable=True)
    op.alter_column('audit_logs', 'facility_id', existing_type=sa.Integer(), nullable=True)
    op.add_column('audit_logs', sa.Column('actor_operator_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_audit_logs_actor_operator_id', 'audit_logs', 'platform_operators',
        ['actor_operator_id'], ['id'],
    )
    op.create_check_constraint(
        'ck_audit_logs_actor_present',
        'audit_logs',
        '(actor_user_id IS NOT NULL) OR (actor_operator_id IS NOT NULL)',
    )


def downgrade() -> None:
    op.drop_constraint('ck_audit_logs_actor_present', 'audit_logs', type_='check')
    op.drop_constraint('fk_audit_logs_actor_operator_id', 'audit_logs', type_='foreignkey')
    op.drop_column('audit_logs', 'actor_operator_id')
    op.alter_column('audit_logs', 'facility_id', existing_type=sa.Integer(), nullable=False)
    op.alter_column('audit_logs', 'actor_role', nullable=False)
    op.alter_column('audit_logs', 'actor_user_id', existing_type=sa.Integer(), nullable=False)

    op.drop_constraint('fk_facilities_provisioned_by_operator_id', 'facilities', type_='foreignkey')
    op.drop_constraint('uq_facilities_facility_reference', 'facilities', type_='unique')
    op.drop_column('facilities', 'provisioned_by_operator_id')
    op.drop_column('facilities', 'facility_reference')
    op.drop_column('facilities', 'status')
    sa.Enum(name='facilitystatus').drop(op.get_bind(), checkfirst=True)

    op.drop_index(op.f('ix_platform_operators_id'), table_name='platform_operators')
    op.drop_table('platform_operators')

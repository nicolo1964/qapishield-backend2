"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2024-12-22

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create facilities table
    op.create_table(
        'facilities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('license_number', sa.String(length=100), nullable=False),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=2), nullable=True),
        sa.Column('zip_code', sa.String(length=10), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('bed_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('license_number')
    )
    op.create_index(op.f('ix_facilities_id'), 'facilities', ['id'], unique=False)

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('role', sa.Enum('admin', 'don', 'mds', 'nurse', name='userrole'), nullable=False),
        sa.Column('facility_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['facility_id'], ['facilities.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)

    # Create residents table
    op.create_table(
        'residents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reference_id', sa.String(length=50), nullable=False),
        sa.Column('facility_id', sa.Integer(), nullable=False),
        sa.Column('admission_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('unit', sa.String(length=100), nullable=True),
        sa.Column('room_number', sa.String(length=20), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['facility_id'], ['facilities.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_residents_id'), 'residents', ['id'], unique=False)
    op.create_index(op.f('ix_residents_reference_id'), 'residents', ['reference_id'], unique=False)

    # Create assessments table
    op.create_table(
        'assessments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('resident_id', sa.Integer(), nullable=False),
        sa.Column('facility_id', sa.Integer(), nullable=False),
        sa.Column('assessment_type', sa.String(length=50), nullable=False),
        sa.Column('risk_level', sa.Enum('low', 'moderate', 'high', name='risklevel'), nullable=False),
        sa.Column('risk_score', sa.Float(), nullable=True),
        sa.Column('risk_factors', sa.Text(), nullable=True),
        sa.Column('recommendations', sa.Text(), nullable=True),
        sa.Column('care_plan', sa.Text(), nullable=True),
        sa.Column('assessed_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['assessed_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['facility_id'], ['facilities.id'], ),
        sa.ForeignKeyConstraint(['resident_id'], ['residents.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_assessments_id'), 'assessments', ['id'], unique=False)

    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), nullable=False),
        sa.Column('actor_role', sa.Enum('admin', 'don', 'mds', 'nurse', name='userrole', create_type=False), nullable=False),
        sa.Column('action_type', sa.Enum('read', 'create', 'update', 'delete', name='auditactiontype'), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=True),
        sa.Column('facility_id', sa.Integer(), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('request_id', sa.String(length=36), nullable=False),
        sa.Column('outcome', sa.Enum('success', 'failure', name='auditoutcome'), nullable=False),
        sa.Column('changed_fields', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['facility_id'], ['facilities.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)
    op.create_index('ix_audit_logs_facility_id', 'audit_logs', ['facility_id'], unique=False)
    op.create_index('ix_audit_logs_actor_user_id', 'audit_logs', ['actor_user_id'], unique=False)
    op.create_index('ix_audit_logs_resource', 'audit_logs', ['resource_type', 'resource_id'], unique=False)
    op.create_index('ix_audit_logs_timestamp', 'audit_logs', ['timestamp'], unique=False)

    # Append-only enforcement: reject UPDATE/DELETE on audit_logs at the database
    # level, even for the table owner. Trigger syntax is engine-specific.
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("""
            CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'audit_logs is append-only: % is not permitted', TG_OP;
            END;
            $$ LANGUAGE plpgsql;
        """)
        op.execute("""
            CREATE TRIGGER audit_logs_no_update
            BEFORE UPDATE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_modification();
        """)
        op.execute("""
            CREATE TRIGGER audit_logs_no_delete
            BEFORE DELETE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_modification();
        """)
    elif bind.dialect.name == 'sqlite':
        op.execute("""
            CREATE TRIGGER audit_logs_no_update
            BEFORE UPDATE ON audit_logs
            BEGIN
                SELECT RAISE(ABORT, 'audit_logs is append-only: UPDATE is not permitted');
            END;
        """)
        op.execute("""
            CREATE TRIGGER audit_logs_no_delete
            BEFORE DELETE ON audit_logs
            BEGIN
                SELECT RAISE(ABORT, 'audit_logs is append-only: DELETE is not permitted');
            END;
        """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("DROP TRIGGER IF EXISTS audit_logs_no_delete ON audit_logs;")
        op.execute("DROP TRIGGER IF EXISTS audit_logs_no_update ON audit_logs;")
        op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_modification();")
    elif bind.dialect.name == 'sqlite':
        op.execute("DROP TRIGGER IF EXISTS audit_logs_no_delete;")
        op.execute("DROP TRIGGER IF EXISTS audit_logs_no_update;")
    op.drop_index('ix_audit_logs_timestamp', table_name='audit_logs')
    op.drop_index('ix_audit_logs_resource', table_name='audit_logs')
    op.drop_index('ix_audit_logs_actor_user_id', table_name='audit_logs')
    op.drop_index('ix_audit_logs_facility_id', table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_id'), table_name='audit_logs')
    op.drop_table('audit_logs')
    if bind.dialect.name == 'postgresql':
        op.execute("DROP TYPE IF EXISTS auditoutcome;")
        op.execute("DROP TYPE IF EXISTS auditactiontype;")

    op.drop_index(op.f('ix_assessments_id'), table_name='assessments')
    op.drop_table('assessments')
    op.drop_index(op.f('ix_residents_reference_id'), table_name='residents')
    op.drop_index(op.f('ix_residents_id'), table_name='residents')
    op.drop_table('residents')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_facilities_id'), table_name='facilities')
    op.drop_table('facilities')

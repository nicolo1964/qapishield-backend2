"""
Pytest configuration and shared fixtures.

Ordering here is load-bearing: env vars must be set, the enum column bugs
patched, and the test database migrated to head BEFORE `app.main` is ever
imported — importing it runs `Base.metadata.create_all()` immediately at
module level, which must land on a database that's already correctly
migrated (real Alembic migrations, not create_all, are what create the
Postgres-specific append-only triggers this app relies on).

Production's `userrole`/`risklevel` Postgres enum types ended up with
uppercase labels (via an out-of-band `create_all()` race), so
`User.role`/`Assessment.risk_level`/`AuditLog.actor_role` intentionally
have no `values_callable` in source — SQLAlchemy's default sends the
enum member's `.name` (uppercase), matching production's actual live
types. This test database is built cleanly via real Alembic migrations,
so it has the labels migration 001 actually declares (lowercase) —
these three columns are patched here, test-process-only, to send
lowercase so they match this test database.
"""
import os
import secrets

# --- 1. Env overrides, before any app.* import -----------------------------
TEST_DATABASE_URL = "postgresql+psycopg://postgres:1234@localhost:5432/qapishield_test?sslmode=disable"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["SECRET_KEY"] = "test_secret_key_do_not_use_in_production_1234567890"
os.environ["LOGIN_RATE_LIMIT"] = "1000/minute"
os.environ["REGISTER_RATE_LIMIT"] = "1000/hour"
os.environ["PUBLIC_REGISTRATION_ENABLED"] = "True"
os.environ["SENTRY_DSN"] = ""  # never send test-generated errors to a real Sentry project

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import sessionmaker
import psycopg

# --- 2. Enum column fixes, test-process-only (app/models/models.py is never edited) ---
import app.models.models as models

models.User.__table__.c.role.type = SAEnum(
    models.UserRole, values_callable=lambda x: [e.value for e in x], name="userrole"
)
models.Assessment.__table__.c.risk_level.type = SAEnum(
    models.RiskLevel, values_callable=lambda x: [e.value for e in x], name="risklevel"
)
models.AuditLog.__table__.c.actor_role.type = SAEnum(
    models.UserRole, values_callable=lambda x: [e.value for e in x], name="userrole"
)

# --- 3. Create + migrate the test database, before app.main is imported ----
def _create_test_database_if_missing():
    conn = psycopg.connect("postgresql://postgres:1234@localhost:5432/postgres", autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", ("qapishield_test",))
            if not cur.fetchone():
                cur.execute("CREATE DATABASE qapishield_test")
    finally:
        conn.close()


def _migrate_test_database():
    from alembic import command
    from alembic.config import Config as AlembicConfig

    alembic_ini = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
    cfg = AlembicConfig(alembic_ini)
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(cfg, "head")


_create_test_database_if_missing()
_migrate_test_database()

# --- 4. Now safe to import the app -----------------------------------------
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash
from app.models.models import Facility, PlatformOperator, User, UserRole, Subscription, SubscriptionStatus

engine = create_engine(TEST_DATABASE_URL)
TestSessionLocal = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def mock_email(monkeypatch):
    """register()/invite-staff/forgot-password queue real SMTP sends via
    BackgroundTasks, which execute synchronously under TestClient — mock the
    low-level sender so tests never attempt real network I/O."""
    monkeypatch.setattr("app.services.email.send_email", lambda *a, **k: None)


@pytest.fixture
def db_session():
    """One connection-level transaction per test, with a SAVEPOINT restarted
    after every app-level `db.commit()`, so nothing the test (or the code
    under test) commits ever escapes the outer transaction. Rolling back an
    INSERT-only sequence also never conflicts with audit_logs' append-only
    trigger (which only blocks UPDATE/DELETE)."""
    connection = engine.connect()
    outer_transaction = connection.begin()
    session = TestSessionLocal(bind=connection)

    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, trans):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    yield session

    session.close()
    outer_transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def facility(db_session):
    f = Facility(name="Test Facility", license_number=f"TEST-{secrets.token_hex(4)}")
    db_session.add(f)
    db_session.flush()
    return f


def make_user(db_session, facility, role, **overrides):
    defaults = dict(
        email=f"{role.value}-{secrets.token_hex(4)}@test.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name=f"Test {role.value.title()}",
        role=role,
        facility_id=facility.id,
        is_active=True,
        is_verified=True,
    )
    defaults.update(overrides)
    user = User(**defaults)
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def admin_user(db_session, facility):
    return make_user(db_session, facility, UserRole.ADMIN)


@pytest.fixture
def don_user(db_session, facility):
    return make_user(db_session, facility, UserRole.DON)


@pytest.fixture
def mds_user(db_session, facility):
    return make_user(db_session, facility, UserRole.MDS)


@pytest.fixture
def nurse_user(db_session, facility):
    return make_user(db_session, facility, UserRole.NURSE)


@pytest.fixture
def active_subscription(db_session, facility):
    sub = Subscription(facility_id=facility.id, status=SubscriptionStatus.ACTIVE)
    db_session.add(sub)
    db_session.flush()
    return sub


def auth_headers(user) -> dict:
    token = create_access_token({"sub": str(user.id), "facility_id": user.facility_id})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def platform_operator(db_session):
    """A platform operator with a known raw key, for exercising the
    operator-only provisioning endpoint. Returns (operator, raw_key,
    headers) since the raw key only ever exists at creation time."""
    import hashlib
    raw_key = f"test-operator-key-{secrets.token_hex(16)}"
    operator = PlatformOperator(
        name="Test Operator",
        key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
        is_active=True,
    )
    db_session.add(operator)
    db_session.flush()
    headers = {"X-Operator-Id": str(operator.id), "X-Operator-Key": raw_key}
    return operator, raw_key, headers

"""
Auth flow tests: register, login (incl. lockout), refresh (incl. reuse
detection), invite-staff (RBAC).
"""
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.models import RefreshToken, User, UserRole
from tests.conftest import auth_headers, make_user


REGISTER_PAYLOAD = {
    "email": "new-admin@test.com",
    "password": "StrongPass123!",
    "full_name": "New Admin",
    "facility_name": "Sunrise SNF",
    "facility_license_number": "LIC-001",
}


# --- register ---------------------------------------------------------------

def test_register_happy_path(client, db_session):
    response = client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert response.status_code == 201

    body = response.json()
    assert body["email"] == REGISTER_PAYLOAD["email"]
    assert body["role"] == "admin"

    user = db_session.query(User).filter(User.email == REGISTER_PAYLOAD["email"]).first()
    assert user is not None
    assert user.is_verified is False


def test_register_disabled_by_default_returns_403(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", False)

    response = client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert response.status_code == 403

    user = db_session.query(User).filter(User.email == REGISTER_PAYLOAD["email"]).first()
    assert user is None


def test_register_is_not_published_in_openapi(client):
    schema = client.app.openapi()
    assert "/api/v1/auth/register" not in schema["paths"]


def test_register_duplicate_email_rejected(client, facility, db_session):
    make_user(db_session, facility, UserRole.ADMIN, email=REGISTER_PAYLOAD["email"])
    db_session.commit()

    response = client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert response.status_code == 400


def test_register_duplicate_license_rejected(client, facility, db_session):
    facility.license_number = REGISTER_PAYLOAD["facility_license_number"]
    db_session.commit()

    response = client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert response.status_code == 400


# --- login --------------------------------------------------------------

def test_login_happy_path(client, facility, db_session):
    make_user(db_session, facility, UserRole.ADMIN, email="loginok@test.com")
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        data={"username": "loginok@test.com", "password": "TestPass123!"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_login_wrong_password_rejected(client, facility, db_session):
    make_user(db_session, facility, UserRole.ADMIN, email="wrongpw@test.com")
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        data={"username": "wrongpw@test.com", "password": "NotTheRightPassword!"},
    )
    assert response.status_code == 401


def test_login_locks_account_after_threshold_failures(client, facility, db_session):
    make_user(db_session, facility, UserRole.ADMIN, email="lockout@test.com")
    db_session.commit()

    for _ in range(settings.LOGIN_LOCKOUT_THRESHOLD):
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "lockout@test.com", "password": "WrongPassword!"},
        )
        assert response.status_code == 401

    locked_response = client.post(
        "/api/v1/auth/login",
        data={"username": "lockout@test.com", "password": "TestPass123!"},
    )
    assert locked_response.status_code == 423
    assert locked_response.json()["detail"]["error_code"] == "ACCOUNT_LOCKED"


def test_login_unverified_user_rejected(client, facility, db_session):
    make_user(db_session, facility, UserRole.ADMIN, email="unverified@test.com", is_verified=False)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        data={"username": "unverified@test.com", "password": "TestPass123!"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["error_code"] == "EMAIL_NOT_VERIFIED"


# --- refresh --------------------------------------------------------------

def _login(client, email):
    response = client.post(
        "/api/v1/auth/login", data={"username": email, "password": "TestPass123!"}
    )
    assert response.status_code == 200
    return response.json()


def test_refresh_rotates_token(client, facility, db_session):
    make_user(db_session, facility, UserRole.ADMIN, email="refresh@test.com")
    db_session.commit()
    tokens = _login(client, "refresh@test.com")

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 200
    new_tokens = response.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    reuse_old = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reuse_old.status_code == 401


def test_refresh_reuse_revokes_all_user_tokens(client, facility, db_session):
    make_user(db_session, facility, UserRole.ADMIN, email="reuse@test.com")
    db_session.commit()
    tokens = _login(client, "reuse@test.com")

    first = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert first.status_code == 200
    new_refresh_token = first.json()["refresh_token"]

    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert replay.status_code == 401

    now_also_revoked = client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh_token})
    assert now_also_revoked.status_code == 401


def test_refresh_expired_token_rejected(client, facility, db_session):
    user = make_user(db_session, facility, UserRole.ADMIN, email="expired@test.com")
    db_session.commit()

    from app.core.security import generate_refresh_token

    raw_token, token_hash = generate_refresh_token()
    db_session.add(RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    ))
    db_session.commit()

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": raw_token})
    assert response.status_code == 401


# --- invite-staff --------------------------------------------------------

def test_invite_staff_as_admin_succeeds(client, facility, db_session, active_subscription):
    admin = make_user(db_session, facility, UserRole.ADMIN)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/invite-staff",
        json={"email": "newnurse@test.com", "full_name": "New Nurse", "role": "nurse"},
        headers=auth_headers(admin),
    )
    assert response.status_code == 201
    assert response.json()["role"] == "nurse"


def test_invite_staff_as_don_rejected(client, facility, db_session, active_subscription):
    don = make_user(db_session, facility, UserRole.DON)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/invite-staff",
        json={"email": "newnurse2@test.com", "full_name": "New Nurse", "role": "nurse"},
        headers=auth_headers(don),
    )
    assert response.status_code == 403


def test_invite_staff_as_nurse_rejected(client, facility, db_session, active_subscription):
    nurse = make_user(db_session, facility, UserRole.NURSE)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/invite-staff",
        json={"email": "newnurse3@test.com", "full_name": "New Nurse", "role": "nurse"},
        headers=auth_headers(nurse),
    )
    assert response.status_code == 403


def test_invite_staff_role_admin_rejected(client, facility, db_session, active_subscription):
    admin = make_user(db_session, facility, UserRole.ADMIN)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/invite-staff",
        json={"email": "anotheradmin@test.com", "full_name": "Another Admin", "role": "admin"},
        headers=auth_headers(admin),
    )
    assert response.status_code == 400


def test_invite_staff_duplicate_email_rejected(client, facility, db_session, active_subscription):
    admin = make_user(db_session, facility, UserRole.ADMIN)
    make_user(db_session, facility, UserRole.NURSE, email="existing@test.com")
    db_session.commit()

    response = client.post(
        "/api/v1/auth/invite-staff",
        json={"email": "existing@test.com", "full_name": "Dup Nurse", "role": "nurse"},
        headers=auth_headers(admin),
    )
    assert response.status_code == 400

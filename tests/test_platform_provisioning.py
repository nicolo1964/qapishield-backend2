"""
Tests for the operator-only facility provisioning endpoint
(POST /api/v1/platform/facilities/provision).

Covers every guarantee required for this feature:
  - unauthenticated / wrong-role callers are denied with NO database write
  - only a distinct platform operator (never a facility User of any role)
    can provision a facility
  - a valid request creates exactly one pending facility + one initial
    Administrator invitation
  - retrying the same facility_reference is idempotent (no duplicates)
  - public self-service registration stays disabled throughout
  - audit entries are created with safe metadata only (no PHI/tokens/secrets)
"""
import json

from app.core.config import settings
from app.models.models import AuditLog, Facility, FacilityStatus, User, UserRole
from tests.conftest import auth_headers, make_user

PROVISION_URL = "/api/v1/platform/facilities/provision"

VALID_PAYLOAD = {
    "facility_reference": "SALES-REF-0001",
    "facility_name": "Meadow Oaks SNF",
    "facility_license_number": "LIC-PROV-0001",
    "facility_bed_count": 120,
    "admin_email": "new-admin@test.com",
    "admin_full_name": "Synthetic Admin",
}


def _table_counts(db_session):
    return (
        db_session.query(Facility).count(),
        db_session.query(User).count(),
    )


# --- public registration stays disabled throughout ---------------------------

def test_public_registration_disabled_during_provisioning_tests(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", False)
    response = client.post("/api/v1/auth/register", json={
        "email": "random-visitor@test.com",
        "password": "StrongPass123!",
        "full_name": "Random Visitor",
        "facility_name": "Uninvited Facility",
        "facility_license_number": "LIC-UNINVITED-0001",
    })
    assert response.status_code == 403
    assert db_session.query(User).filter(User.email == "random-visitor@test.com").first() is None


# --- unauthenticated / wrong-actor denial, no DB write ------------------------

def test_unauthenticated_caller_denied_no_db_write(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", False)
    before = _table_counts(db_session)

    response = client.post(PROVISION_URL, json=VALID_PAYLOAD)

    assert response.status_code == 401
    assert _table_counts(db_session) == before


def test_missing_operator_key_denied_no_db_write(client, db_session, monkeypatch, platform_operator):
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", False)
    operator, raw_key, headers = platform_operator
    before = _table_counts(db_session)

    bad_headers = {"X-Operator-Id": str(operator.id)}  # key omitted
    response = client.post(PROVISION_URL, json=VALID_PAYLOAD, headers=bad_headers)

    assert response.status_code == 401
    assert _table_counts(db_session) == before


def test_wrong_operator_key_denied_no_db_write(client, db_session, monkeypatch, platform_operator):
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", False)
    operator, raw_key, headers = platform_operator
    before = _table_counts(db_session)

    bad_headers = {"X-Operator-Id": str(operator.id), "X-Operator-Key": "totally-wrong-key"}
    response = client.post(PROVISION_URL, json=VALID_PAYLOAD, headers=bad_headers)

    assert response.status_code == 401
    assert _table_counts(db_session) == before


def test_inactive_operator_denied_no_db_write(client, db_session, monkeypatch, platform_operator):
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", False)
    operator, raw_key, headers = platform_operator
    operator.is_active = False
    db_session.flush()
    before = _table_counts(db_session)

    response = client.post(PROVISION_URL, json=VALID_PAYLOAD, headers=headers)

    assert response.status_code == 401
    assert _table_counts(db_session) == before


# --- facility-scoped Users of every role are denied, no DB write -------------

def _assert_facility_user_denied(client, db_session, monkeypatch, facility, role):
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", False)
    user = make_user(db_session, facility, role)
    before = _table_counts(db_session)

    # A facility user's own valid JWT is sent as a Bearer token, exactly as
    # they would use it against any other endpoint -- it must not be
    # treated as operator authorization on this endpoint (which doesn't
    # even inspect the Authorization header).
    response = client.post(PROVISION_URL, json=VALID_PAYLOAD, headers=auth_headers(user))

    assert response.status_code == 401
    assert _table_counts(db_session) == before


def test_admin_user_denied_no_db_write(client, db_session, monkeypatch, facility):
    _assert_facility_user_denied(client, db_session, monkeypatch, facility, UserRole.ADMIN)


def test_don_user_denied_no_db_write(client, db_session, monkeypatch, facility):
    _assert_facility_user_denied(client, db_session, monkeypatch, facility, UserRole.DON)


def test_mds_user_denied_no_db_write(client, db_session, monkeypatch, facility):
    _assert_facility_user_denied(client, db_session, monkeypatch, facility, UserRole.MDS)


def test_nurse_user_denied_no_db_write(client, db_session, monkeypatch, facility):
    _assert_facility_user_denied(client, db_session, monkeypatch, facility, UserRole.NURSE)


def test_admin_user_operator_headers_combined_with_jwt_still_denied(client, db_session, monkeypatch, facility, platform_operator):
    """An Admin can't escalate by simply also sending a stolen/guessed
    operator id alongside their own JWT -- the key must still match."""
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", False)
    admin = make_user(db_session, facility, UserRole.ADMIN)
    operator, raw_key, _ = platform_operator
    before = _table_counts(db_session)

    headers = {**auth_headers(admin), "X-Operator-Id": str(operator.id), "X-Operator-Key": "guessed-wrong"}
    response = client.post(PROVISION_URL, json=VALID_PAYLOAD, headers=headers)

    assert response.status_code == 401
    assert _table_counts(db_session) == before


# --- valid operator request: happy path --------------------------------------

def test_valid_operator_request_creates_pending_facility_and_invite(client, db_session, monkeypatch, platform_operator):
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", False)
    operator, raw_key, headers = platform_operator

    response = client.post(PROVISION_URL, json=VALID_PAYLOAD, headers=headers)

    assert response.status_code == 201
    body = response.json()
    assert body["facility_reference"] == VALID_PAYLOAD["facility_reference"]
    assert body["facility_status"] == "pending"
    assert body["admin_invite_status"] == "sent"
    assert body["idempotent_replay"] is False

    facility = db_session.query(Facility).filter(
        Facility.facility_reference == VALID_PAYLOAD["facility_reference"]
    ).first()
    assert facility is not None
    assert facility.status == FacilityStatus.PENDING
    assert facility.provisioned_by_operator_id == operator.id

    admin_user = db_session.query(User).filter(User.email == VALID_PAYLOAD["admin_email"]).first()
    assert admin_user is not None
    assert admin_user.role == UserRole.ADMIN
    assert admin_user.facility_id == facility.id
    assert admin_user.is_verified is False  # operator never verifies on the admin's behalf

    # The operator never sees/sets a usable password: the placeholder hash
    # cannot possibly equal any real submitted password.
    from app.core.security import verify_password
    assert verify_password("", admin_user.hashed_password) is False
    assert verify_password(VALID_PAYLOAD["admin_email"], admin_user.hashed_password) is False


def test_valid_operator_request_creates_exactly_one_facility_and_one_admin(client, db_session, monkeypatch, platform_operator):
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", False)
    operator, raw_key, headers = platform_operator
    before_facilities, before_users = _table_counts(db_session)

    response = client.post(PROVISION_URL, json=VALID_PAYLOAD, headers=headers)
    assert response.status_code == 201

    after_facilities, after_users = _table_counts(db_session)
    assert after_facilities == before_facilities + 1
    assert after_users == before_users + 1


# --- idempotency ---------------------------------------------------------------

def test_retrying_same_facility_reference_is_idempotent(client, db_session, monkeypatch, platform_operator):
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", False)
    operator, raw_key, headers = platform_operator

    first = client.post(PROVISION_URL, json=VALID_PAYLOAD, headers=headers)
    assert first.status_code == 201
    first_body = first.json()

    before_facilities, before_users = _table_counts(db_session)

    second = client.post(PROVISION_URL, json=VALID_PAYLOAD, headers=headers)
    assert second.status_code == 201
    second_body = second.json()

    after_facilities, after_users = _table_counts(db_session)

    assert after_facilities == before_facilities
    assert after_users == before_users
    assert second_body["facility_id"] == first_body["facility_id"]
    assert second_body["idempotent_replay"] is True
    assert second_body["admin_invite_status"] == "already_sent"


# --- audit logging: safe metadata only ----------------------------------------

def test_successful_provision_creates_audit_entry_attributed_to_operator(client, db_session, monkeypatch, platform_operator):
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", False)
    operator, raw_key, headers = platform_operator

    response = client.post(PROVISION_URL, json=VALID_PAYLOAD, headers=headers)
    assert response.status_code == 201
    facility_id = response.json()["facility_id"]

    entry = db_session.query(AuditLog).filter(
        AuditLog.resource_type == "platform_facility_provision",
        AuditLog.resource_id == facility_id,
    ).first()
    assert entry is not None
    assert entry.actor_operator_id == operator.id
    assert entry.actor_user_id is None
    assert entry.outcome.value == "success"
    assert entry.facility_id == facility_id


def test_no_audit_or_response_fixture_contains_phi_tokens_or_secrets(client, db_session, monkeypatch, platform_operator):
    """
    Guards against accidental leakage: nothing in the audit trail or the
    HTTP response for a provisioning call should contain the admin's raw
    email/name, the operator's raw key, a password, or an invite token --
    only safe references (ids, statuses, generic strings).
    """
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", False)
    operator, raw_key, headers = platform_operator

    response = client.post(PROVISION_URL, json=VALID_PAYLOAD, headers=headers)
    assert response.status_code == 201

    response_text = json.dumps(response.json())
    assert VALID_PAYLOAD["admin_email"] not in response_text
    assert VALID_PAYLOAD["admin_full_name"] not in response_text
    assert raw_key not in response_text

    entries = db_session.query(AuditLog).filter(
        AuditLog.resource_type == "platform_facility_provision",
    ).all()
    assert len(entries) >= 1
    for entry in entries:
        serialized = json.dumps({
            "resource_type": entry.resource_type,
            "resource_id": entry.resource_id,
            "outcome": entry.outcome.value,
            "changed_fields": entry.changed_fields,
            "action_type": entry.action_type.value,
        })
        assert VALID_PAYLOAD["admin_email"] not in serialized
        assert VALID_PAYLOAD["admin_full_name"] not in serialized
        assert raw_key not in serialized
        assert "password" not in serialized.lower()


# --- conflict handling: generic errors, no internal detail leaked ------------

def test_duplicate_license_number_returns_generic_error_no_new_facility(client, db_session, monkeypatch, platform_operator, facility):
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", False)
    operator, raw_key, headers = platform_operator
    before_facilities, _ = _table_counts(db_session)

    payload = {**VALID_PAYLOAD, "facility_reference": "SALES-REF-CONFLICT", "facility_license_number": facility.license_number}
    response = client.post(PROVISION_URL, json=payload, headers=headers)

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "SQL" not in detail and "Traceback" not in detail
    assert db_session.query(Facility).count() == before_facilities

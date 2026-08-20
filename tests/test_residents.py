"""
Resident endpoint tests: create/list/get/deactivate — RBAC, facility
scoping, subscription gating, and an audit-log spot check.
"""
from app.models.models import AuditActionType, AuditLog, AuditOutcome, Resident, UserRole
from tests.conftest import auth_headers, make_user


RESIDENT_PAYLOAD = {"reference_id": "REF-001", "unit": "2A", "room_number": "204"}


# --- create ---------------------------------------------------------------

def test_create_resident_as_admin_succeeds(client, facility, db_session, active_subscription):
    admin = make_user(db_session, facility, UserRole.ADMIN)
    db_session.commit()

    response = client.post("/api/v1/residents/", json=RESIDENT_PAYLOAD, headers=auth_headers(admin))
    assert response.status_code == 201
    assert response.json()["reference_id"] == RESIDENT_PAYLOAD["reference_id"]


def test_create_resident_as_don_succeeds(client, facility, db_session, active_subscription):
    don = make_user(db_session, facility, UserRole.DON)
    db_session.commit()

    response = client.post("/api/v1/residents/", json=RESIDENT_PAYLOAD, headers=auth_headers(don))
    assert response.status_code == 201


def test_create_resident_as_nurse_rejected(client, facility, db_session, active_subscription):
    nurse = make_user(db_session, facility, UserRole.NURSE)
    db_session.commit()

    response = client.post("/api/v1/residents/", json=RESIDENT_PAYLOAD, headers=auth_headers(nurse))
    assert response.status_code == 403


def test_create_resident_as_mds_rejected(client, facility, db_session, active_subscription):
    mds = make_user(db_session, facility, UserRole.MDS)
    db_session.commit()

    response = client.post("/api/v1/residents/", json=RESIDENT_PAYLOAD, headers=auth_headers(mds))
    assert response.status_code == 403


def test_create_resident_duplicate_reference_id_rejected(client, facility, db_session, active_subscription):
    admin = make_user(db_session, facility, UserRole.ADMIN)
    db_session.add(Resident(reference_id=RESIDENT_PAYLOAD["reference_id"], facility_id=facility.id))
    db_session.commit()

    response = client.post("/api/v1/residents/", json=RESIDENT_PAYLOAD, headers=auth_headers(admin))
    assert response.status_code == 400


def test_create_resident_without_active_subscription_rejected(client, facility, db_session):
    admin = make_user(db_session, facility, UserRole.ADMIN)
    db_session.commit()

    response = client.post("/api/v1/residents/", json=RESIDENT_PAYLOAD, headers=auth_headers(admin))
    assert response.status_code == 402
    assert response.json()["detail"]["error_code"] == "SUBSCRIPTION_INACTIVE"


def test_create_resident_logs_audit_event(client, facility, db_session, active_subscription):
    admin = make_user(db_session, facility, UserRole.ADMIN)
    db_session.commit()

    response = client.post("/api/v1/residents/", json=RESIDENT_PAYLOAD, headers=auth_headers(admin))
    assert response.status_code == 201
    resident_id = response.json()["id"]

    log = db_session.query(AuditLog).filter(
        AuditLog.resource_type == "resident",
        AuditLog.resource_id == resident_id,
        AuditLog.action_type == AuditActionType.CREATE,
    ).first()
    assert log is not None
    assert log.outcome == AuditOutcome.SUCCESS
    assert log.actor_user_id == admin.id
    assert log.facility_id == facility.id


# --- list / get -------------------------------------------------------------

def test_list_residents_happy_path(client, facility, db_session):
    nurse = make_user(db_session, facility, UserRole.NURSE)
    db_session.add(Resident(reference_id="REF-LIST", facility_id=facility.id))
    db_session.commit()

    response = client.get("/api/v1/residents/", headers=auth_headers(nurse))
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_get_resident_from_other_facility_returns_404(client, facility, db_session):
    nurse = make_user(db_session, facility, UserRole.NURSE)

    from app.models.models import Facility

    other_facility = Facility(name="Other SNF", license_number="OTHER-LIC")
    db_session.add(other_facility)
    db_session.flush()
    other_resident = Resident(reference_id="REF-OTHER", facility_id=other_facility.id)
    db_session.add(other_resident)
    db_session.commit()

    response = client.get(f"/api/v1/residents/{other_resident.id}", headers=auth_headers(nurse))
    assert response.status_code == 404


def test_get_resident_happy_path(client, facility, db_session):
    nurse = make_user(db_session, facility, UserRole.NURSE)
    resident = Resident(reference_id="REF-GET", facility_id=facility.id)
    db_session.add(resident)
    db_session.commit()

    response = client.get(f"/api/v1/residents/{resident.id}", headers=auth_headers(nurse))
    assert response.status_code == 200
    assert response.json()["reference_id"] == "REF-GET"


# --- deactivate -------------------------------------------------------------

def test_deactivate_resident_as_admin_succeeds(client, facility, db_session, active_subscription):
    admin = make_user(db_session, facility, UserRole.ADMIN)
    resident = Resident(reference_id="REF-DEACT", facility_id=facility.id)
    db_session.add(resident)
    db_session.commit()

    response = client.patch(f"/api/v1/residents/{resident.id}/deactivate", headers=auth_headers(admin))
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_deactivate_resident_as_nurse_rejected(client, facility, db_session, active_subscription):
    nurse = make_user(db_session, facility, UserRole.NURSE)
    resident = Resident(reference_id="REF-DEACT2", facility_id=facility.id)
    db_session.add(resident)
    db_session.commit()

    response = client.patch(f"/api/v1/residents/{resident.id}/deactivate", headers=auth_headers(nurse))
    assert response.status_code == 403


def test_deactivate_nonexistent_resident_returns_404(client, facility, db_session, active_subscription):
    admin = make_user(db_session, facility, UserRole.ADMIN)
    db_session.commit()

    response = client.patch("/api/v1/residents/999999/deactivate", headers=auth_headers(admin))
    assert response.status_code == 404

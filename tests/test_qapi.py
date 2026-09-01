"""
QAPI dashboard endpoint tests: restricted to DON/MDS/Admin (clinical
roles), plus read audit logging.
"""
from app.models.models import AuditActionType, AuditLog, AuditOutcome, Resident, UserRole
from tests.conftest import auth_headers, make_user


def _make_resident(db_session, facility, reference_id="REF-Q1"):
    resident = Resident(reference_id=reference_id, facility_id=facility.id)
    db_session.add(resident)
    db_session.flush()
    return resident


# --- dashboard ------------------------------------------------------------

def test_qapi_dashboard_happy_path(client, facility, db_session):
    mds = make_user(db_session, facility, UserRole.MDS)
    _make_resident(db_session, facility)
    db_session.commit()

    response = client.get("/api/v1/qapi/dashboard", headers=auth_headers(mds))
    assert response.status_code == 200
    body = response.json()
    assert body["facility_id"] == facility.id
    assert body["total_residents"] == 1


def test_qapi_dashboard_as_nurse_rejected(client, facility, db_session):
    nurse = make_user(db_session, facility, UserRole.NURSE)
    db_session.commit()

    response = client.get("/api/v1/qapi/dashboard", headers=auth_headers(nurse))
    assert response.status_code == 403


def test_qapi_dashboard_logs_read_audit_event(client, facility, db_session):
    mds = make_user(db_session, facility, UserRole.MDS)
    db_session.commit()

    response = client.get("/api/v1/qapi/dashboard", headers=auth_headers(mds))
    assert response.status_code == 200

    log = db_session.query(AuditLog).filter(
        AuditLog.resource_type == "qapi_dashboard",
        AuditLog.action_type == AuditActionType.READ,
        AuditLog.actor_user_id == mds.id,
    ).first()
    assert log is not None
    assert log.outcome == AuditOutcome.SUCCESS


# --- high-risk-residents --------------------------------------------------

def test_high_risk_residents_happy_path(client, facility, db_session):
    don = make_user(db_session, facility, UserRole.DON)
    db_session.commit()

    response = client.get("/api/v1/qapi/high-risk-residents", headers=auth_headers(don))
    assert response.status_code == 200
    assert response.json() == []


def test_high_risk_residents_as_nurse_rejected(client, facility, db_session):
    nurse = make_user(db_session, facility, UserRole.NURSE)
    db_session.commit()

    response = client.get("/api/v1/qapi/high-risk-residents", headers=auth_headers(nurse))
    assert response.status_code == 403


def test_high_risk_residents_logs_read_audit_event(client, facility, db_session):
    admin = make_user(db_session, facility, UserRole.ADMIN)
    db_session.commit()

    response = client.get("/api/v1/qapi/high-risk-residents", headers=auth_headers(admin))
    assert response.status_code == 200

    log = db_session.query(AuditLog).filter(
        AuditLog.resource_type == "high_risk_residents",
        AuditLog.action_type == AuditActionType.READ,
        AuditLog.actor_user_id == admin.id,
    ).first()
    assert log is not None
    assert log.outcome == AuditOutcome.SUCCESS

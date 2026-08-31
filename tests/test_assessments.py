"""
Assessment endpoint tests: create, care-plan generation, and read
endpoints — restricted to DON/MDS/Admin (clinical roles), facility
scoping, subscription gating, and audit logging.
"""
from app.models.models import (
    Assessment, AuditActionType, AuditLog, AuditOutcome, Facility, Resident, RiskLevel, UserRole,
)
from tests.conftest import auth_headers, make_user


def _make_resident(db_session, facility, reference_id="REF-A1"):
    resident = Resident(reference_id=reference_id, facility_id=facility.id)
    db_session.add(resident)
    db_session.flush()
    return resident


# --- create -----------------------------------------------------------------

def test_create_assessment_happy_path(client, facility, db_session, active_subscription):
    mds = make_user(db_session, facility, UserRole.MDS)
    resident = _make_resident(db_session, facility)
    db_session.commit()

    response = client.post(
        "/api/v1/assessments/",
        json={"resident_id": resident.id, "assessment_type": "falls", "risk_factors": {"history_of_falls": True}},
        headers=auth_headers(mds),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["resident_id"] == resident.id
    assert body["risk_level"] in [level.value for level in RiskLevel]


def test_create_assessment_as_nurse_rejected(client, facility, db_session, active_subscription):
    nurse = make_user(db_session, facility, UserRole.NURSE)
    resident = _make_resident(db_session, facility)
    db_session.commit()

    response = client.post(
        "/api/v1/assessments/",
        json={"resident_id": resident.id, "assessment_type": "falls", "risk_factors": {}},
        headers=auth_headers(nurse),
    )
    assert response.status_code == 403


def test_create_assessment_invalid_type_rejected(client, facility, db_session, active_subscription):
    mds = make_user(db_session, facility, UserRole.MDS)
    resident = _make_resident(db_session, facility)
    db_session.commit()

    response = client.post(
        "/api/v1/assessments/",
        json={"resident_id": resident.id, "assessment_type": "not_a_real_type", "risk_factors": {}},
        headers=auth_headers(mds),
    )
    assert response.status_code == 400


def test_create_assessment_resident_in_other_facility_returns_404(client, facility, db_session, active_subscription):
    mds = make_user(db_session, facility, UserRole.MDS)

    other_facility = Facility(name="Other SNF", license_number="OTHER-LIC-2")
    db_session.add(other_facility)
    db_session.flush()
    other_resident = Resident(reference_id="REF-OTHER-2", facility_id=other_facility.id)
    db_session.add(other_resident)
    db_session.commit()

    response = client.post(
        "/api/v1/assessments/",
        json={"resident_id": other_resident.id, "assessment_type": "falls", "risk_factors": {}},
        headers=auth_headers(mds),
    )
    assert response.status_code == 404


def test_create_assessment_logs_audit_event(client, facility, db_session, active_subscription):
    mds = make_user(db_session, facility, UserRole.MDS)
    resident = _make_resident(db_session, facility)
    db_session.commit()

    response = client.post(
        "/api/v1/assessments/",
        json={"resident_id": resident.id, "assessment_type": "falls", "risk_factors": {}},
        headers=auth_headers(mds),
    )
    assert response.status_code == 201
    assessment_id = response.json()["id"]

    log = db_session.query(AuditLog).filter(
        AuditLog.resource_type == "assessment",
        AuditLog.resource_id == assessment_id,
        AuditLog.action_type == AuditActionType.CREATE,
    ).first()
    assert log is not None
    assert log.outcome == AuditOutcome.SUCCESS
    assert log.actor_user_id == mds.id


def test_create_assessment_without_active_subscription_rejected(client, facility, db_session):
    mds = make_user(db_session, facility, UserRole.MDS)
    resident = _make_resident(db_session, facility)
    db_session.commit()

    response = client.post(
        "/api/v1/assessments/",
        json={"resident_id": resident.id, "assessment_type": "falls", "risk_factors": {}},
        headers=auth_headers(mds),
    )
    assert response.status_code == 402
    assert response.json()["detail"]["error_code"] == "SUBSCRIPTION_INACTIVE"


# --- care-plan ----------------------------------------------------------

def _make_assessment(db_session, facility, resident, user):
    from app.services.risk_assessment import assess_risk

    risk_level, risk_score, risk_factors_json, recommendations_json = assess_risk("falls", {"history_of_falls": True})
    assessment = Assessment(
        resident_id=resident.id,
        facility_id=facility.id,
        assessment_type="falls",
        risk_level=risk_level,
        risk_score=risk_score,
        risk_factors=risk_factors_json,
        recommendations=recommendations_json,
        assessed_by=user.id,
    )
    db_session.add(assessment)
    db_session.flush()
    return assessment


def test_generate_care_plan_happy_path(client, facility, db_session, active_subscription):
    mds = make_user(db_session, facility, UserRole.MDS)
    resident = _make_resident(db_session, facility)
    assessment = _make_assessment(db_session, facility, resident, mds)
    db_session.commit()

    response = client.post(
        "/api/v1/assessments/care-plan",
        json={"assessment_id": assessment.id},
        headers=auth_headers(mds),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["assessment_id"] == assessment.id
    assert body["care_plan"]


def test_generate_care_plan_as_nurse_rejected(client, facility, db_session, active_subscription):
    nurse = make_user(db_session, facility, UserRole.NURSE)
    resident = _make_resident(db_session, facility)
    assessment = _make_assessment(db_session, facility, resident, nurse)
    db_session.commit()

    response = client.post(
        "/api/v1/assessments/care-plan",
        json={"assessment_id": assessment.id},
        headers=auth_headers(nurse),
    )
    assert response.status_code == 403


def test_generate_care_plan_not_found_returns_404(client, facility, db_session, active_subscription):
    mds = make_user(db_session, facility, UserRole.MDS)
    db_session.commit()

    response = client.post(
        "/api/v1/assessments/care-plan",
        json={"assessment_id": 999999},
        headers=auth_headers(mds),
    )
    assert response.status_code == 404


# --- list / get ---------------------------------------------------------

def test_get_resident_assessments_happy_path(client, facility, db_session, active_subscription):
    mds = make_user(db_session, facility, UserRole.MDS)
    resident = _make_resident(db_session, facility)
    _make_assessment(db_session, facility, resident, mds)
    db_session.commit()

    response = client.get(f"/api/v1/assessments/resident/{resident.id}", headers=auth_headers(mds))
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_get_resident_assessments_as_nurse_rejected(client, facility, db_session, active_subscription):
    nurse = make_user(db_session, facility, UserRole.NURSE)
    resident = _make_resident(db_session, facility)
    db_session.commit()

    response = client.get(f"/api/v1/assessments/resident/{resident.id}", headers=auth_headers(nurse))
    assert response.status_code == 403


def test_get_resident_assessments_logs_read_audit_event(client, facility, db_session, active_subscription):
    mds = make_user(db_session, facility, UserRole.MDS)
    resident = _make_resident(db_session, facility)
    _make_assessment(db_session, facility, resident, mds)
    db_session.commit()

    response = client.get(f"/api/v1/assessments/resident/{resident.id}", headers=auth_headers(mds))
    assert response.status_code == 200

    log = db_session.query(AuditLog).filter(
        AuditLog.resource_type == "assessment",
        AuditLog.action_type == AuditActionType.READ,
        AuditLog.actor_user_id == mds.id,
    ).first()
    assert log is not None
    assert log.outcome == AuditOutcome.SUCCESS


def test_get_resident_assessments_facility_scoping(client, facility, db_session, active_subscription):
    mds = make_user(db_session, facility, UserRole.MDS)

    other_facility = Facility(name="Other SNF 2", license_number="OTHER-LIC-3")
    db_session.add(other_facility)
    db_session.flush()
    other_resident = Resident(reference_id="REF-OTHER-3", facility_id=other_facility.id)
    db_session.add(other_resident)
    db_session.commit()

    response = client.get(f"/api/v1/assessments/resident/{other_resident.id}", headers=auth_headers(mds))
    assert response.status_code == 404


def test_get_assessment_happy_path(client, facility, db_session, active_subscription):
    mds = make_user(db_session, facility, UserRole.MDS)
    resident = _make_resident(db_session, facility)
    assessment = _make_assessment(db_session, facility, resident, mds)
    db_session.commit()

    response = client.get(f"/api/v1/assessments/{assessment.id}", headers=auth_headers(mds))
    assert response.status_code == 200
    assert response.json()["id"] == assessment.id


def test_get_assessment_as_nurse_rejected(client, facility, db_session, active_subscription):
    nurse = make_user(db_session, facility, UserRole.NURSE)
    resident = _make_resident(db_session, facility)
    assessment = _make_assessment(db_session, facility, resident, nurse)
    db_session.commit()

    response = client.get(f"/api/v1/assessments/{assessment.id}", headers=auth_headers(nurse))
    assert response.status_code == 403


def test_get_assessment_logs_read_audit_event(client, facility, db_session, active_subscription):
    mds = make_user(db_session, facility, UserRole.MDS)
    resident = _make_resident(db_session, facility)
    assessment = _make_assessment(db_session, facility, resident, mds)
    db_session.commit()

    response = client.get(f"/api/v1/assessments/{assessment.id}", headers=auth_headers(mds))
    assert response.status_code == 200

    log = db_session.query(AuditLog).filter(
        AuditLog.resource_type == "assessment",
        AuditLog.resource_id == assessment.id,
        AuditLog.action_type == AuditActionType.READ,
    ).first()
    assert log is not None
    assert log.outcome == AuditOutcome.SUCCESS


def test_generate_care_plan_logs_update_audit_event(client, facility, db_session, active_subscription):
    mds = make_user(db_session, facility, UserRole.MDS)
    resident = _make_resident(db_session, facility)
    assessment = _make_assessment(db_session, facility, resident, mds)
    db_session.commit()

    response = client.post(
        "/api/v1/assessments/care-plan",
        json={"assessment_id": assessment.id},
        headers=auth_headers(mds),
    )
    assert response.status_code == 200

    log = db_session.query(AuditLog).filter(
        AuditLog.resource_type == "assessment",
        AuditLog.resource_id == assessment.id,
        AuditLog.action_type == AuditActionType.UPDATE,
    ).first()
    assert log is not None
    assert log.outcome == AuditOutcome.SUCCESS
    assert log.changed_fields == '["care_plan"]'


def test_get_assessment_from_other_facility_returns_404(client, facility, db_session, active_subscription):
    mds = make_user(db_session, facility, UserRole.MDS)

    other_facility = Facility(name="Other SNF 3", license_number="OTHER-LIC-4")
    db_session.add(other_facility)
    db_session.flush()
    other_resident = Resident(reference_id="REF-OTHER-4", facility_id=other_facility.id)
    db_session.add(other_resident)
    db_session.flush()
    other_assessment = _make_assessment(db_session, other_facility, other_resident, mds)
    db_session.commit()

    response = client.get(f"/api/v1/assessments/{other_assessment.id}", headers=auth_headers(mds))
    assert response.status_code == 404

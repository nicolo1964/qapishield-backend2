"""
Operator-only platform endpoints.

This router is deliberately NOT a public customer-facing feature: it is
mounted with include_in_schema=False in app/main.py so it never appears in
/docs, /redoc, or /openapi.json, and it is authorized exclusively via
require_platform_operator (a distinct credential channel from user JWTs --
see app/api/deps.py). No facility Administrator, of any role, can ever
satisfy this dependency.

Workflow this implements (see PR description / operator runbook for the
full sales-approved sequence):
  1. Sales/ops verifies a signed agreement + pre-PHI onboarding checklist
     OUTSIDE this app.
  2. An authorized operator calls this endpoint once per approved facility.
  3. A facility row is created (status=PENDING) and the initial
     Administrator invitation is created/sent via the existing
     invite-token/accept-invite mechanics -- no password ever touches this
     endpoint.
  4. The Administrator accepts the invite, verifies email if required, and
     completes Stripe Checkout via the existing billing flow.
  5. The existing Stripe webhook flips Subscription.status to ACTIVE, which
     is what actually gates facility-scoped access via
     require_active_subscription -- this endpoint does not and cannot
     bypass that gate.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.api.deps import require_platform_operator
from app.models.models import (
    AuditActionType,
    AuditOutcome,
    Facility,
    FacilityStatus,
    PlatformOperator,
    User,
    UserRole,
)
from app.schemas.schemas import FacilityProvisionRequest, FacilityProvisionResponse
from app.services.audit import log_audit_event
from app.services.invitations import create_staff_invite

router = APIRouter()


@router.post(
    "/facilities/provision",
    response_model=FacilityProvisionResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("30/hour")
async def provision_facility(
    request: Request,
    body: FacilityProvisionRequest,
    background_tasks: BackgroundTasks,
    operator: PlatformOperator = Depends(require_platform_operator),
    db: Session = Depends(get_db),
):
    """
    Provision a new facility (sales-approved onboarding only) and send the
    initial Administrator an invitation via the existing secure
    staff-invitation flow. Idempotent on facility_reference: repeating the
    same approved request returns the existing result rather than creating
    duplicates.
    """
    # --- Idempotent replay: same facility_reference already provisioned ---
    existing = db.query(Facility).filter(Facility.facility_reference == body.facility_reference).first()
    if existing:
        log_audit_event(
            db,
            request=request,
            operator=operator,
            action_type=AuditActionType.CREATE,
            resource_type="platform_facility_provision",
            resource_id=existing.id,
            facility_id=existing.id,
            outcome=AuditOutcome.SUCCESS,
            changed_fields=["idempotent_replay"],
        )
        db.commit()
        return FacilityProvisionResponse(
            facility_id=existing.id,
            facility_reference=existing.facility_reference,
            facility_status=existing.status,
            admin_invite_status="already_sent",
            idempotent_replay=True,
        )

    # --- Conflict checks: generic errors, no internal detail leaked ---
    license_conflict = db.query(Facility).filter(
        Facility.license_number == body.facility_license_number
    ).first()
    if license_conflict:
        log_audit_event(
            db,
            request=request,
            operator=operator,
            action_type=AuditActionType.CREATE,
            resource_type="platform_facility_provision",
            outcome=AuditOutcome.FAILURE,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to provision facility with the supplied details",
        )

    email_conflict = db.query(User).filter(User.email == body.admin_email).first()
    if email_conflict:
        log_audit_event(
            db,
            request=request,
            operator=operator,
            action_type=AuditActionType.CREATE,
            resource_type="platform_facility_provision",
            outcome=AuditOutcome.FAILURE,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to provision facility with the supplied details",
        )

    # --- Create the facility (status=PENDING; access remains gated by the
    # existing Subscription.status, unaffected by this field) ---
    facility = Facility(
        name=body.facility_name,
        license_number=body.facility_license_number,
        bed_count=body.facility_bed_count,
        status=FacilityStatus.PENDING,
        facility_reference=body.facility_reference,
        provisioned_by_operator_id=operator.id,
    )
    db.add(facility)
    db.flush()  # assign facility.id within this transaction

    invite_result = create_staff_invite(
        db, background_tasks,
        email=body.admin_email, full_name=body.admin_full_name, role=UserRole.ADMIN,
        facility_id=facility.id,
    )

    log_audit_event(
        db,
        request=request,
        operator=operator,
        action_type=AuditActionType.CREATE,
        resource_type="platform_facility_provision",
        resource_id=facility.id,
        facility_id=facility.id,
        outcome=AuditOutcome.SUCCESS,
    )
    db.commit()

    return FacilityProvisionResponse(
        facility_id=facility.id,
        facility_reference=facility.facility_reference,
        facility_status=facility.status,
        admin_invite_status="already_sent" if invite_result.already_existed else "sent",
        idempotent_replay=False,
    )

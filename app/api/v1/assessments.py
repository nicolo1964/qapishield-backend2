"""
Risk assessment and care plan endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.models import Assessment, AuditActionType, AuditOutcome, Resident, User, UserRole
from app.schemas.schemas import AssessmentCreate, AssessmentResponse, CarePlanRequest, CarePlanResponse
from app.api.deps import require_active_subscription, require_role
from app.services.audit import log_audit_event
from app.services.risk_assessment import assess_risk, generate_care_plan
import json

router = APIRouter()

@router.post("/", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    assessment_data: AssessmentCreate,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.DON, UserRole.MDS, action_type=AuditActionType.CREATE, resource_type="assessment")),
    _subscription: User = Depends(require_active_subscription),
    db: Session = Depends(get_db)
):
    """
    Create a new risk assessment for a resident
    Returns risk level (Low/Moderate/High) with explanations
    """
    # Verify resident belongs to user's facility
    resident = db.query(Resident).filter(
        Resident.id == assessment_data.resident_id,
        Resident.facility_id == current_user.facility_id
    ).first()

    if not resident:
        log_audit_event(
            db, request=request, user=current_user,
            action_type=AuditActionType.CREATE, resource_type="assessment",
            outcome=AuditOutcome.FAILURE,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resident not found in your facility"
        )

    # Validate assessment type
    valid_types = ["falls", "pressure_ulcers", "infection", "readmission"]
    if assessment_data.assessment_type not in valid_types:
        log_audit_event(
            db, request=request, user=current_user,
            action_type=AuditActionType.CREATE, resource_type="assessment",
            outcome=AuditOutcome.FAILURE,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid assessment type. Must be one of: {', '.join(valid_types)}"
        )

    # Calculate risk
    risk_level, risk_score, risk_factors_json, recommendations_json = assess_risk(
        assessment_data.assessment_type,
        assessment_data.risk_factors
    )

    # Create assessment record
    assessment = Assessment(
        resident_id=assessment_data.resident_id,
        facility_id=current_user.facility_id,
        assessment_type=assessment_data.assessment_type,
        risk_level=risk_level,
        risk_score=risk_score,
        risk_factors=risk_factors_json,
        recommendations=recommendations_json,
        assessed_by=current_user.id
    )

    db.add(assessment)
    db.flush()

    log_audit_event(
        db, request=request, user=current_user,
        action_type=AuditActionType.CREATE, resource_type="assessment",
        resource_id=assessment.id, outcome=AuditOutcome.SUCCESS,
    )

    db.commit()
    db.refresh(assessment)

    return assessment

@router.post("/care-plan", response_model=CarePlanResponse)
async def generate_care_plan_endpoint(
    body: CarePlanRequest,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.DON, UserRole.MDS, action_type=AuditActionType.UPDATE, resource_type="assessment")),
    _subscription: User = Depends(require_active_subscription),
    db: Session = Depends(get_db)
):
    """
    Generate AI-powered care plan for an assessment
    """
    # Get assessment
    assessment = db.query(Assessment).filter(
        Assessment.id == body.assessment_id,
        Assessment.facility_id == current_user.facility_id
    ).first()

    if not assessment:
        log_audit_event(
            db, request=request, user=current_user,
            action_type=AuditActionType.UPDATE, resource_type="assessment",
            resource_id=body.assessment_id, outcome=AuditOutcome.FAILURE,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )

    # Parse risk factors and recommendations
    risk_factors = json.loads(assessment.risk_factors)
    recommendations = json.loads(assessment.recommendations)

    # Generate care plan
    care_plan = generate_care_plan(
        assessment.assessment_type,
        assessment.risk_level,
        risk_factors,
        recommendations
    )

    # Update assessment with care plan
    assessment.care_plan = care_plan

    log_audit_event(
        db, request=request, user=current_user,
        action_type=AuditActionType.UPDATE, resource_type="assessment",
        resource_id=assessment.id, outcome=AuditOutcome.SUCCESS,
        changed_fields=["care_plan"],
    )

    db.commit()

    return {
        "assessment_id": assessment.id,
        "care_plan": care_plan
    }

@router.get("/resident/{resident_id}", response_model=List[AssessmentResponse])
async def get_resident_assessments(
    resident_id: int,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.DON, UserRole.MDS, action_type=AuditActionType.READ, resource_type="assessment")),
    db: Session = Depends(get_db)
):
    """
    Get all assessments for a specific resident
    """
    # Verify resident belongs to user's facility
    resident = db.query(Resident).filter(
        Resident.id == resident_id,
        Resident.facility_id == current_user.facility_id
    ).first()

    if not resident:
        log_audit_event(
            db, request=request, user=current_user,
            action_type=AuditActionType.READ, resource_type="assessment",
            outcome=AuditOutcome.FAILURE,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resident not found in your facility"
        )

    assessments = db.query(Assessment).filter(
        Assessment.resident_id == resident_id
    ).order_by(Assessment.created_at.desc()).all()

    log_audit_event(
        db, request=request, user=current_user,
        action_type=AuditActionType.READ, resource_type="assessment",
        outcome=AuditOutcome.SUCCESS,
    )
    db.commit()

    return assessments

@router.get("/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(
    assessment_id: int,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.DON, UserRole.MDS, action_type=AuditActionType.READ, resource_type="assessment")),
    db: Session = Depends(get_db)
):
    """
    Get a specific assessment by ID
    """
    assessment = db.query(Assessment).filter(
        Assessment.id == assessment_id,
        Assessment.facility_id == current_user.facility_id
    ).first()

    if not assessment:
        log_audit_event(
            db, request=request, user=current_user,
            action_type=AuditActionType.READ, resource_type="assessment",
            resource_id=assessment_id, outcome=AuditOutcome.FAILURE,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )

    log_audit_event(
        db, request=request, user=current_user,
        action_type=AuditActionType.READ, resource_type="assessment",
        resource_id=assessment.id, outcome=AuditOutcome.SUCCESS,
    )
    db.commit()

    return assessment

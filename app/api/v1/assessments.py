"""
Risk assessment and care plan endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.models import Assessment, Resident, User
from app.schemas.schemas import AssessmentCreate, AssessmentResponse, CarePlanRequest, CarePlanResponse
from app.api.v1.auth import get_current_user
from app.services.risk_assessment import assess_risk, generate_care_plan
import json

router = APIRouter()

@router.post("/", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    assessment_data: AssessmentCreate,
    current_user: User = Depends(get_current_user),
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resident not found in your facility"
        )
    
    # Validate assessment type
    valid_types = ["falls", "pressure_ulcers", "infection", "readmission"]
    if assessment_data.assessment_type not in valid_types:
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
    db.commit()
    db.refresh(assessment)
    
    return assessment

@router.post("/care-plan", response_model=CarePlanResponse)
async def generate_care_plan_endpoint(
    request: CarePlanRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate AI-powered care plan for an assessment
    """
    # Get assessment
    assessment = db.query(Assessment).filter(
        Assessment.id == request.assessment_id,
        Assessment.facility_id == current_user.facility_id
    ).first()
    
    if not assessment:
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
    db.commit()
    
    return {
        "assessment_id": assessment.id,
        "care_plan": care_plan
    }

@router.get("/resident/{resident_id}", response_model=List[AssessmentResponse])
async def get_resident_assessments(
    resident_id: int,
    current_user: User = Depends(get_current_user),
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resident not found in your facility"
        )
    
    assessments = db.query(Assessment).filter(
        Assessment.resident_id == resident_id
    ).order_by(Assessment.created_at.desc()).all()
    
    return assessments

@router.get("/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(
    assessment_id: int,
    current_user: User = Depends(get_current_user),
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )
    
    return assessment

"""
QAPI Dashboard endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.core.database import get_db
from app.models.models import Assessment, Resident, User, RiskLevel
from app.schemas.schemas import QAPIDashboardResponse, AssessmentResponse
from app.api.v1.auth import get_current_user
from typing import List

router = APIRouter()

@router.get("/dashboard", response_model=QAPIDashboardResponse)
async def get_qapi_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get QAPI dashboard with facility-wide counts and high-risk summaries
    """
    facility_id = current_user.facility_id
    
    # Total and active residents
    total_residents = db.query(func.count(Resident.id)).filter(
        Resident.facility_id == facility_id
    ).scalar()
    
    active_residents = db.query(func.count(Resident.id)).filter(
        Resident.facility_id == facility_id,
        Resident.is_active == True
    ).scalar()
    
    # Risk level counts (from most recent assessments)
    high_risk_count = db.query(func.count(Assessment.id)).filter(
        Assessment.facility_id == facility_id,
        Assessment.risk_level == RiskLevel.HIGH
    ).scalar()
    
    moderate_risk_count = db.query(func.count(Assessment.id)).filter(
        Assessment.facility_id == facility_id,
        Assessment.risk_level == RiskLevel.MODERATE
    ).scalar()
    
    low_risk_count = db.query(func.count(Assessment.id)).filter(
        Assessment.facility_id == facility_id,
        Assessment.risk_level == RiskLevel.LOW
    ).scalar()
    
    # Recent assessments (last 10)
    recent_assessments = db.query(Assessment).filter(
        Assessment.facility_id == facility_id
    ).order_by(desc(Assessment.created_at)).limit(10).all()
    
    # Risk breakdown by assessment type
    risk_breakdown = {}
    for assessment_type in ["falls", "pressure_ulcers", "infection", "readmission"]:
        type_counts = {
            "high": db.query(func.count(Assessment.id)).filter(
                Assessment.facility_id == facility_id,
                Assessment.assessment_type == assessment_type,
                Assessment.risk_level == RiskLevel.HIGH
            ).scalar(),
            "moderate": db.query(func.count(Assessment.id)).filter(
                Assessment.facility_id == facility_id,
                Assessment.assessment_type == assessment_type,
                Assessment.risk_level == RiskLevel.MODERATE
            ).scalar(),
            "low": db.query(func.count(Assessment.id)).filter(
                Assessment.facility_id == facility_id,
                Assessment.assessment_type == assessment_type,
                Assessment.risk_level == RiskLevel.LOW
            ).scalar()
        }
        risk_breakdown[assessment_type] = type_counts
    
    return {
        "facility_id": facility_id,
        "total_residents": total_residents or 0,
        "active_residents": active_residents or 0,
        "high_risk_count": high_risk_count or 0,
        "moderate_risk_count": moderate_risk_count or 0,
        "low_risk_count": low_risk_count or 0,
        "recent_assessments": recent_assessments,
        "risk_breakdown": risk_breakdown
    }

@router.get("/high-risk-residents")
async def get_high_risk_residents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of residents with high-risk assessments
    """
    facility_id = current_user.facility_id
    
    # Get unique residents with high-risk assessments
    high_risk_assessments = db.query(Assessment).filter(
        Assessment.facility_id == facility_id,
        Assessment.risk_level == RiskLevel.HIGH
    ).order_by(desc(Assessment.created_at)).all()
    
    # Group by resident
    residents_data = {}
    for assessment in high_risk_assessments:
        if assessment.resident_id not in residents_data:
            resident = db.query(Resident).filter(Resident.id == assessment.resident_id).first()
            residents_data[assessment.resident_id] = {
                "resident": {
                    "id": resident.id,
                    "reference_id": resident.reference_id,
                    "unit": resident.unit,
                    "room_number": resident.room_number
                },
                "high_risk_assessments": []
            }
        
        residents_data[assessment.resident_id]["high_risk_assessments"].append({
            "id": assessment.id,
            "assessment_type": assessment.assessment_type,
            "risk_score": assessment.risk_score,
            "created_at": assessment.created_at
        })
    
    return list(residents_data.values())

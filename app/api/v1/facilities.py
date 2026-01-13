"""
Facility management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.models import Facility, User
from app.schemas.schemas import FacilityResponse
from app.api.v1.auth import get_current_user

router = APIRouter()

@router.get("/me", response_model=FacilityResponse)
async def get_my_facility(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's facility information
    """
    facility = db.query(Facility).filter(Facility.id == current_user.facility_id).first()
    
    if not facility:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Facility not found"
        )
    
    return facility

@router.get("/{facility_id}", response_model=FacilityResponse)
async def get_facility(
    facility_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get facility by ID (must be user's own facility)
    """
    if current_user.facility_id != facility_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this facility"
        )
    
    facility = db.query(Facility).filter(Facility.id == facility_id).first()
    
    if not facility:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Facility not found"
        )
    
    return facility

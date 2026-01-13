"""
Resident management endpoints (de-identified, PHI-free)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.models import Resident, User
from app.schemas.schemas import ResidentCreate, ResidentResponse
from app.api.v1.auth import get_current_user

router = APIRouter()

@router.post("/", response_model=ResidentResponse, status_code=status.HTTP_201_CREATED)
async def create_resident(
    resident_data: ResidentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a new resident using de-identified Reference ID only (no PHI)
    """
    # Check if reference_id already exists in this facility
    existing = db.query(Resident).filter(
        Resident.reference_id == resident_data.reference_id,
        Resident.facility_id == current_user.facility_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resident with this reference ID already exists in your facility"
        )
    
    resident = Resident(
        reference_id=resident_data.reference_id,
        facility_id=current_user.facility_id,
        admission_date=resident_data.admission_date,
        unit=resident_data.unit,
        room_number=resident_data.room_number
    )
    
    db.add(resident)
    db.commit()
    db.refresh(resident)
    
    return resident

@router.get("/", response_model=List[ResidentResponse])
async def list_residents(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all residents in current user's facility
    """
    query = db.query(Resident).filter(Resident.facility_id == current_user.facility_id)
    
    if active_only:
        query = query.filter(Resident.is_active == True)
    
    residents = query.offset(skip).limit(limit).all()
    return residents

@router.get("/{resident_id}", response_model=ResidentResponse)
async def get_resident(
    resident_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get resident by ID (must be in user's facility)
    """
    resident = db.query(Resident).filter(
        Resident.id == resident_id,
        Resident.facility_id == current_user.facility_id
    ).first()
    
    if not resident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resident not found"
        )
    
    return resident

@router.patch("/{resident_id}/deactivate", response_model=ResidentResponse)
async def deactivate_resident(
    resident_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Deactivate a resident (discharge)
    """
    resident = db.query(Resident).filter(
        Resident.id == resident_id,
        Resident.facility_id == current_user.facility_id
    ).first()
    
    if not resident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resident not found"
        )
    
    resident.is_active = False
    db.commit()
    db.refresh(resident)
    
    return resident

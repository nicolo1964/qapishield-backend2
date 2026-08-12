"""
Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from app.models.models import UserRole, RiskLevel

# Auth schemas
class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    facility_name: str
    facility_license_number: str
    facility_bed_count: Optional[int] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[int] = None
    facility_id: Optional[int] = None

class ResendVerificationRequest(BaseModel):
    email: EmailStr

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class MessageResponse(BaseModel):
    message: str

class StaffInviteRequest(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole

class AcceptInviteRequest(BaseModel):
    token: str
    password: str

# Facility schemas
class FacilityCreate(BaseModel):
    name: str
    license_number: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    phone: Optional[str] = None
    bed_count: Optional[int] = None

class FacilityResponse(BaseModel):
    id: int
    name: str
    license_number: str
    bed_count: Optional[int]
    created_at: datetime
    
    class Config:
        from_attributes = True

# Resident schemas
class ResidentCreate(BaseModel):
    reference_id: str
    admission_date: Optional[datetime] = None
    unit: Optional[str] = None
    room_number: Optional[str] = None

class ResidentResponse(BaseModel):
    id: int
    reference_id: str
    facility_id: int
    admission_date: Optional[datetime]
    unit: Optional[str]
    room_number: Optional[str]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# Assessment schemas
class AssessmentCreate(BaseModel):
    resident_id: int
    assessment_type: str  # falls, pressure_ulcers, infection, readmission
    risk_factors: dict

class AssessmentResponse(BaseModel):
    id: int
    resident_id: int
    assessment_type: str
    risk_level: RiskLevel
    risk_score: Optional[float]
    risk_factors: str
    recommendations: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class CarePlanRequest(BaseModel):
    assessment_id: int

class CarePlanResponse(BaseModel):
    assessment_id: int
    care_plan: str

# QAPI Dashboard schemas
class QAPIDashboardResponse(BaseModel):
    facility_id: int
    total_residents: int
    active_residents: int
    high_risk_count: int
    moderate_risk_count: int
    low_risk_count: int
    recent_assessments: List[AssessmentResponse]
    risk_breakdown: dict

# User schemas
class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    role: UserRole
    facility_id: int
    is_active: bool
    is_verified: bool

    class Config:
        from_attributes = True

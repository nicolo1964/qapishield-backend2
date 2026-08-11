"""
SQLAlchemy database models
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text, Float, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    DON = "don"
    MDS = "mds"
    NURSE = "nurse"

class RiskLevel(str, enum.Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"

class AuditActionType(str, enum.Enum):
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"

class AuditOutcome(str, enum.Enum):
    SUCCESS = "success"
    FAILURE = "failure"

class Facility(Base):
    __tablename__ = "facilities"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    license_number = Column(String(100), unique=True, nullable=False)
    address = Column(String(500))
    city = Column(String(100))
    state = Column(String(2))
    zip_code = Column(String(10))
    phone = Column(String(20))
    bed_count = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    users = relationship("User", back_populates="facility")
    residents = relationship("Resident", back_populates="facility")
    assessments = relationship("Assessment", back_populates="facility")

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(Enum(UserRole), nullable=False)
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    verification_sent_at = Column(DateTime(timezone=True), nullable=True)
    verification_reminder_sent_at = Column(DateTime(timezone=True), nullable=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    facility = relationship("Facility", back_populates="users")

class Resident(Base):
    __tablename__ = "residents"
    
    id = Column(Integer, primary_key=True, index=True)
    reference_id = Column(String(50), nullable=False, index=True)  # De-identified ID only
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    admission_date = Column(DateTime(timezone=True))
    unit = Column(String(100))
    room_number = Column(String(20))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    facility = relationship("Facility", back_populates="residents")
    assessments = relationship("Assessment", back_populates="resident")

class Assessment(Base):
    __tablename__ = "assessments"
    
    id = Column(Integer, primary_key=True, index=True)
    resident_id = Column(Integer, ForeignKey("residents.id"), nullable=False)
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    assessment_type = Column(String(50), nullable=False)  # falls, pressure_ulcers, infection, readmission
    risk_level = Column(Enum(RiskLevel), nullable=False)
    risk_score = Column(Float)
    risk_factors = Column(Text)  # JSON string of risk factors
    recommendations = Column(Text)  # JSON string of recommendations
    care_plan = Column(Text)  # AI-generated care plan
    assessed_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    resident = relationship("Resident", back_populates="assessments")
    facility = relationship("Facility", back_populates="assessments")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    actor_role = Column(Enum(UserRole, values_callable=lambda x: [e.value for e in x]), nullable=False)
    action_type = Column(Enum(AuditActionType, values_callable=lambda x: [e.value for e in x]), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(Integer, nullable=True)
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    ip_address = Column(String(45), nullable=True)
    request_id = Column(String(36), nullable=False)
    outcome = Column(Enum(AuditOutcome, values_callable=lambda x: [e.value for e in x]), nullable=False)
    changed_fields = Column(Text, nullable=True)  # JSON array of field names only, never values

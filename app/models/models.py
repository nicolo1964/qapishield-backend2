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

class SubscriptionStatus(str, enum.Enum):
    PENDING_PAYMENT = "pending_payment"
    ACTIVE = "active"
    SUSPENDED = "suspended"

class FacilityStatus(str, enum.Enum):
    """
    Informational only — does NOT gate access. Access continues to be
    governed exclusively by Subscription.status via require_active_subscription.
    This exists so operators/sales can see at a glance whether a
    provisioned facility's Administrator has accepted their invite yet.
    """
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"

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
    stripe_customer_id = Column(String(255), nullable=True)
    # values_callable: send lowercase .value (not the member .name) — this is
    # a brand-new column/enum type with no legacy production mismatch to
    # work around (unlike User.role, see tests/conftest.py's docstring).
    status = Column(
        Enum(FacilityStatus, values_callable=lambda x: [e.value for e in x], name="facilitystatus"),
        nullable=True,
    )  # informational only, see FacilityStatus docstring
    facility_reference = Column(String(100), unique=True, nullable=True)  # operator-supplied idempotency key
    provisioned_by_operator_id = Column(Integer, ForeignKey("platform_operators.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    users = relationship("User", back_populates="facility")
    residents = relationship("Resident", back_populates="facility")
    assessments = relationship("Assessment", back_populates="facility")
    subscription = relationship("Subscription", uselist=False, back_populates="facility")

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
    # Exactly one of actor_user_id / actor_operator_id is set on every row
    # (enforced by ck_audit_logs_actor_present) — a facility-scoped User
    # action vs. a platform-operator action are never conflated.
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    actor_role = Column(Enum(UserRole), nullable=True)
    actor_operator_id = Column(Integer, ForeignKey("platform_operators.id"), nullable=True)
    action_type = Column(Enum(AuditActionType, values_callable=lambda x: [e.value for e in x]), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(Integer, nullable=True)
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=True)
    ip_address = Column(String(45), nullable=True)
    request_id = Column(String(36), nullable=False)
    outcome = Column(Enum(AuditOutcome, values_callable=lambda x: [e.value for e in x]), nullable=False)
    changed_fields = Column(Text, nullable=True)  # JSON array of field names only, never values

class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, index=True)
    stripe_product_id = Column(String(255), nullable=False)
    stripe_price_id = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(String(500), nullable=True)
    amount = Column(Integer, nullable=False)  # cents
    currency = Column(String(10), nullable=False)
    interval = Column(String(20), nullable=False)  # e.g. "month"
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    subscriptions = relationship("Subscription", back_populates="plan")

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    facility_id = Column(Integer, ForeignKey("facilities.id"), unique=True, nullable=False)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    status = Column(
        Enum(SubscriptionStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SubscriptionStatus.PENDING_PAYMENT,
    )
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    facility = relationship("Facility", back_populates="subscription")
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")

class PlatformOperator(Base):
    """
    Distinct credential store for QAPIShield staff who provision facilities.
    Deliberately NOT part of the users/facilities model — a facility
    Administrator's JWT can never satisfy platform-operator authorization,
    because this table (and the header-based auth checked against it) is a
    completely separate credential channel from the OAuth2/JWT user login.
    """
    __tablename__ = "platform_operators"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)  # human label only, e.g. "Deborah - Sales Ops"
    key_hash = Column(String(64), unique=True, nullable=False)  # sha256 hex digest of the raw operator key
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False)  # sha256 hex digest
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

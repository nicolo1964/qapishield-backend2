"""
Authentication endpoints
"""
import hashlib
import secrets
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token, decode_access_token
from app.core.rate_limit import limiter
from app.api.deps import require_role
from app.models.models import AuditActionType, User, Facility, UserRole
from app.schemas.schemas import (
    UserLogin, UserRegister, Token, UserResponse,
    ResendVerificationRequest, ForgotPasswordRequest, ResetPasswordRequest, MessageResponse,
    StaffInviteRequest, AcceptInviteRequest,
)
from app.services.email import (
    send_verification_email, send_password_reset_email, send_staff_invite_email,
    build_verification_link, build_password_reset_link, build_invite_link,
)
from datetime import datetime, timedelta, timezone
from app.core.config import settings

def _password_fingerprint(hashed_password: str) -> str:
    return hashlib.sha256(hashed_password.encode()).hexdigest()[:16]

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.REGISTER_RATE_LIMIT)
async def register(
    request: Request,
    user_data: UserRegister,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Register new facility with admin user (for demo/pilot signups)
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if facility license number already exists
    existing_facility = db.query(Facility).filter(
        Facility.license_number == user_data.facility_license_number
    ).first()
    if existing_facility:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Facility license number already registered"
        )
    
    # Create facility
    facility = Facility(
        name=user_data.facility_name,
        license_number=user_data.facility_license_number,
        bed_count=user_data.facility_bed_count
    )
    db.add(facility)
    db.flush()  # Get facility ID
    
    # Create admin user
    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        role=UserRole.ADMIN,
        facility_id=facility.id
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    user.verification_sent_at = datetime.now(timezone.utc)
    db.commit()

    verification_token = create_access_token(
        {"sub": str(user.id), "purpose": "email_verification"},
        expires_delta=timedelta(hours=settings.VERIFICATION_LINK_EXPIRES_HOURS),
    )
    background_tasks.add_task(
        send_verification_email, user.email, build_verification_link(verification_token)
    )

    return user

@router.post("/login", response_model=Token)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Login with email and password, returns JWT token
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Please verify your email before logging in",
                "error_code": "EMAIL_NOT_VERIFIED",
            },
        )

    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "facility_id": user.facility_id},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/verify-email", response_model=MessageResponse)
async def verify_email(token: str, db: Session = Depends(get_db)):
    """
    Verify a user's email address using the token from their verification link
    """
    payload = decode_access_token(token)
    if not payload or payload.get("purpose") != "email_verification":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification link"
        )

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user.is_verified = True
    db.commit()

    return {"message": "Email verified successfully"}

@router.post("/resend-verification", response_model=MessageResponse)
@limiter.limit("3/hour")
async def resend_verification(
    request: Request,
    body: ResendVerificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Resend a verification email. Always returns a generic response so
    account existence/verification status can't be enumerated.
    """
    user = db.query(User).filter(User.email == body.email).first()
    if user and not user.is_verified:
        user.verification_sent_at = datetime.now(timezone.utc)
        user.verification_reminder_sent_at = None
        db.commit()

        verification_token = create_access_token(
            {"sub": str(user.id), "purpose": "email_verification"},
            expires_delta=timedelta(hours=settings.VERIFICATION_LINK_EXPIRES_HOURS),
        )
        background_tasks.add_task(
            send_verification_email, user.email, build_verification_link(verification_token)
        )

    return {"message": "If that email is registered and unverified, a new verification link has been sent"}

@router.post("/forgot-password", response_model=MessageResponse)
@limiter.limit("5/hour")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Request a password reset link. Always returns a generic response so
    account existence can't be enumerated.
    """
    user = db.query(User).filter(User.email == body.email).first()
    if user:
        reset_token = create_access_token(
            {
                "sub": str(user.id),
                "purpose": "password_reset",
                "pwd_fp": _password_fingerprint(user.hashed_password),
            },
            expires_delta=timedelta(hours=settings.PASSWORD_RESET_EXPIRES_HOURS),
        )
        background_tasks.add_task(
            send_password_reset_email, user.email, build_password_reset_link(reset_token)
        )

    return {"message": "If that email is registered, a password reset link has been sent"}

@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Set a new password using the token from a password reset link
    """
    payload = decode_access_token(body.token)
    if not payload or payload.get("purpose") != "password_reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset link"
        )

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or payload.get("pwd_fp") != _password_fingerprint(user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset link"
        )

    user.hashed_password = get_password_hash(body.new_password)
    db.commit()

    return {"message": "Password reset successfully"}

@router.post("/invite-staff", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/hour")
async def invite_staff(
    request: Request,
    body: StaffInviteRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role(UserRole.ADMIN, action_type=AuditActionType.CREATE, resource_type="user")),
    db: Session = Depends(get_db),
):
    """
    Invite a Nurse/DON/MDS user into the inviting Admin's facility
    """
    if body.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins cannot be invited via this endpoint"
        )

    existing_user = db.query(User).filter(User.email == body.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    placeholder_password = get_password_hash(secrets.token_urlsafe(32))
    user = User(
        email=body.email,
        hashed_password=placeholder_password,
        full_name=body.full_name,
        role=body.role,
        facility_id=current_user.facility_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    invite_token = create_access_token(
        {
            "sub": str(user.id),
            "purpose": "staff_invite",
            "pwd_fp": _password_fingerprint(user.hashed_password),
        },
        expires_delta=timedelta(hours=settings.STAFF_INVITE_EXPIRES_HOURS),
    )
    background_tasks.add_task(
        send_staff_invite_email, user.email, build_invite_link(invite_token)
    )

    return user

@router.post("/accept-invite", response_model=MessageResponse)
async def accept_invite(body: AcceptInviteRequest, db: Session = Depends(get_db)):
    """
    Accept a staff invite by setting a password and activating the account
    """
    payload = decode_access_token(body.token)
    if not payload or payload.get("purpose") != "staff_invite":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invite link"
        )

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or payload.get("pwd_fp") != _password_fingerprint(user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invite link"
        )

    user.hashed_password = get_password_hash(body.password)
    user.is_verified = True
    db.commit()

    return {"message": "Invite accepted successfully"}

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """
    Dependency to get current authenticated user
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    
    return user

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current user information
    """
    return current_user

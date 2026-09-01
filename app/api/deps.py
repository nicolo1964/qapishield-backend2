"""
Shared FastAPI dependencies
"""
import hashlib
import hmac
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.models import AuditActionType, AuditOutcome, PlatformOperator, SubscriptionStatus, User, UserRole
from app.services.audit import log_audit_event

# Defined locally (not imported from app.api.v1.auth) so this module has no
# dependency on a specific route file — avoids a circular import now that
# auth.py itself needs require_role for the staff-invite endpoint.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception

    return user

def require_role(*allowed_roles: UserRole, action_type: AuditActionType, resource_type: str = "resident"):
    """
    Dependency factory: restricts an endpoint to the given roles.
    Denied attempts are recorded as a FAILURE audit event before the 403 is raised.
    """
    def role_checker(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if current_user.role not in allowed_roles:
            raw_resident_id = request.path_params.get("resident_id")
            log_audit_event(
                db,
                request=request,
                user=current_user,
                action_type=action_type,
                resource_type=resource_type,
                resource_id=int(raw_resident_id) if raw_resident_id else None,
                outcome=AuditOutcome.FAILURE,
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker

def require_platform_operator(
    x_operator_id: str = Header(default=None, alias="X-Operator-Id"),
    x_operator_key: str = Header(default=None, alias="X-Operator-Key"),
    db: Session = Depends(get_db),
) -> PlatformOperator:
    """
    Authorizes a platform operator (QAPIShield staff who provision
    facilities) via a distinct header-based credential, entirely separate
    from the OAuth2/JWT user-login channel used by get_current_user. A
    facility Administrator's JWT is never even inspected here, so it can
    never satisfy this dependency — there is structurally no path from
    "has a valid facility-scoped user session" to "is a platform operator".

    Missing/malformed headers and unknown/inactive operators all raise the
    same generic 401 with no DB write, so a caller can't distinguish
    "wrong id" from "wrong key" from "no headers at all".
    """
    denied = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Operator authentication required",
    )
    if not x_operator_id or not x_operator_key:
        raise denied
    try:
        operator_id = int(x_operator_id)
    except ValueError:
        raise denied

    operator = db.query(PlatformOperator).filter(PlatformOperator.id == operator_id).first()
    if not operator or not operator.is_active:
        raise denied

    key_hash = hashlib.sha256(x_operator_key.encode()).hexdigest()
    if not hmac.compare_digest(key_hash, operator.key_hash):
        raise denied

    return operator

def require_active_subscription(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Blocks facility-scoped writes unless the facility's subscription is active.
    Read endpoints and account-management endpoints (login, billing itself, etc.)
    should NOT use this, so a suspended facility's admin can still resolve payment.
    """
    subscription = current_user.facility.subscription
    current_status = subscription.status if subscription else SubscriptionStatus.PENDING_PAYMENT
    if current_status != SubscriptionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": "Your facility's subscription is not active. Please complete or update payment.",
                "error_code": "SUBSCRIPTION_INACTIVE",
                "subscription_status": current_status.value,
            },
        )
    return current_user

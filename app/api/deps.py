"""
Shared FastAPI dependencies
"""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.models import AuditActionType, AuditOutcome, User, UserRole
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

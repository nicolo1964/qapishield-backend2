"""
Shared FastAPI dependencies
"""
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import AuditActionType, AuditOutcome, User, UserRole
from app.api.v1.auth import get_current_user
from app.services.audit import log_audit_event

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

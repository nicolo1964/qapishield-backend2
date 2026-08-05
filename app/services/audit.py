"""
Audit log write helper
"""
import json
from typing import List, Optional
from fastapi import Request
from sqlalchemy.orm import Session
from app.models.models import AuditLog, AuditActionType, AuditOutcome, User

def log_audit_event(
    db: Session,
    *,
    request: Request,
    user: User,
    action_type: AuditActionType,
    resource_type: str,
    outcome: AuditOutcome,
    resource_id: Optional[int] = None,
    changed_fields: Optional[List[str]] = None,
) -> None:
    """
    Record an audit log entry. Caller is responsible for committing the
    transaction (so the entry can be committed atomically with the action
    it describes, or on its own for read-only/denied actions).
    """
    db.add(AuditLog(
        actor_user_id=user.id,
        actor_role=user.role,
        action_type=action_type,
        resource_type=resource_type,
        resource_id=resource_id,
        facility_id=user.facility_id,
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, "request_id", None),
        outcome=outcome,
        changed_fields=json.dumps(changed_fields) if changed_fields else None,
    ))

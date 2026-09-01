"""
Audit log write helper
"""
import json
from typing import List, Optional
from fastapi import Request
from sqlalchemy.orm import Session
from app.models.models import AuditLog, AuditActionType, AuditOutcome, PlatformOperator, User

def log_audit_event(
    db: Session,
    *,
    request: Request,
    action_type: AuditActionType,
    resource_type: str,
    outcome: AuditOutcome,
    user: Optional[User] = None,
    operator: Optional[PlatformOperator] = None,
    facility_id: Optional[int] = None,
    resource_id: Optional[int] = None,
    changed_fields: Optional[List[str]] = None,
) -> None:
    """
    Record an audit log entry. Caller is responsible for committing the
    transaction (so the entry can be committed atomically with the action
    it describes, or on its own for read-only/denied actions).

    Exactly one of `user` / `operator` must be given, matching the
    ck_audit_logs_actor_present DB constraint. Pass `facility_id` explicitly
    for operator-attributed actions (an operator has no facility of their
    own); for user-attributed actions it defaults to the user's facility.
    """
    if (user is None) == (operator is None):
        raise ValueError("log_audit_event requires exactly one of user or operator")

    db.add(AuditLog(
        actor_user_id=user.id if user else None,
        actor_role=user.role if user else None,
        actor_operator_id=operator.id if operator else None,
        action_type=action_type,
        resource_type=resource_type,
        resource_id=resource_id,
        facility_id=facility_id if facility_id is not None else (user.facility_id if user else None),
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, "request_id", None),
        outcome=outcome,
        changed_fields=json.dumps(changed_fields) if changed_fields else None,
    ))

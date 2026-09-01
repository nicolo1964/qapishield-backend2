"""
Shared staff-invitation mechanics: create the invited user row (placeholder,
unusable password), issue the same invite token/link used everywhere else,
and queue the email. Used by both:
  - POST /api/v1/auth/invite-staff (an existing facility Admin inviting a
    peer into their own facility; blocks inviting the ADMIN role)
  - POST /api/v1/platform/facilities/provision (a platform operator
    inviting the *first* Administrator into a brand-new facility)

Factoring this out means the operator-provisioning flow reuses the exact
same token/email/accept-invite mechanics as the existing feature instead of
re-implementing (and potentially diverging from) invite security logic.
Callers are responsible for their own authorization/business rules (e.g.
who is allowed to call this, and which roles they may invite) — this
module only knows how to create one invite.
"""
import secrets
from dataclasses import dataclass
from datetime import timedelta
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.models.models import User, UserRole
from app.services.email import send_staff_invite_email, build_invite_link


def _password_fingerprint(hashed_password: str) -> str:
    import hashlib
    return hashlib.sha256(hashed_password.encode()).hexdigest()[:16]


@dataclass
class StaffInviteResult:
    user: User
    already_existed: bool  # True when idempotent callers found a prior invite for this email


def create_staff_invite(
    db: Session,
    background_tasks: BackgroundTasks,
    *,
    email: str,
    full_name: str,
    role: UserRole,
    facility_id: int,
) -> StaffInviteResult:
    """
    Create the invited user row (with a placeholder, never-usable password),
    issue an invite token, and queue the invite email via the shared
    template/sender. Does NOT check role-specific business rules (e.g.
    "admins can't be invited by peer admins") or authorization — callers
    apply those before calling this.

    If a user with this email already exists, no new row/email is created;
    the existing user is returned with already_existed=True so callers can
    implement idempotent retries without duplicate invitations.
    """
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        return StaffInviteResult(user=existing_user, already_existed=True)

    placeholder_password = get_password_hash(secrets.token_urlsafe(32))
    user = User(
        email=email,
        hashed_password=placeholder_password,
        full_name=full_name,
        role=role,
        facility_id=facility_id,
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

    return StaffInviteResult(user=user, already_existed=False)

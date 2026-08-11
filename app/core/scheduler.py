"""
In-process scheduler for periodic jobs (email verification reminders)
"""
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.services.email import send_verification_reminder_email, build_verification_link

REMINDER_AT_DELTA = timedelta(hours=48)
LINK_EXPIRES_AFTER_HOURS = 72


def send_verification_reminders() -> None:
    # Queries specific columns via raw SQL rather than `db.query(User)` to avoid
    # deserializing the `role` column, which has a pre-existing enum name/value
    # mismatch bug unrelated to this feature (left untouched per instruction).
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        cutoff_start = now - timedelta(hours=LINK_EXPIRES_AFTER_HOURS)
        cutoff_end = now - REMINDER_AT_DELTA

        due = db.execute(
            text("""
                SELECT id, email, verification_sent_at
                FROM users
                WHERE is_verified = false
                  AND verification_sent_at IS NOT NULL
                  AND verification_reminder_sent_at IS NULL
                  AND verification_sent_at <= :cutoff_end
                  AND verification_sent_at > :cutoff_start
            """),
            {"cutoff_end": cutoff_end, "cutoff_start": cutoff_start},
        ).all()

        for row in due:
            remaining = (row.verification_sent_at + timedelta(hours=LINK_EXPIRES_AFTER_HOURS)) - now
            token = create_access_token(
                {"sub": str(row.id), "purpose": "email_verification"},
                expires_delta=remaining,
            )
            send_verification_reminder_email(row.email, build_verification_link(token))
            db.execute(
                text("UPDATE users SET verification_reminder_sent_at = :now WHERE id = :id"),
                {"now": now, "id": row.id},
            )

        db.commit()
    finally:
        db.close()


scheduler = BackgroundScheduler()
scheduler.add_job(send_verification_reminders, "interval", hours=1, id="verification_reminders")

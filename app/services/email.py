"""
SMTP email sending
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.core.config import settings

# Brand palette pulled directly from qapishield.com's compiled CSS
BRAND_BLUE = "#0f3559"
BRAND_GOLD = "#e4b567"
TEXT_COLOR = "#374151"
MUTED_TEXT = "#6b7280"
BORDER_COLOR = "#e5e7eb"
PAGE_BG = "#f4f5f7"
FOOTER_BG = "#f9fafb"


def _render_html_email(heading: str, paragraphs: list, cta_text: str, cta_link: str, footer_note: str) -> str:
    paragraphs_html = "".join(
        f'<p style="margin:0 0 16px 0; font-size:15px; line-height:1.6; color:{TEXT_COLOR};">{p}</p>'
        for p in paragraphs
    )
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background-color:{PAGE_BG}; font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:{PAGE_BG}; padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width:480px; background-color:#ffffff; border-radius:8px; overflow:hidden; border:1px solid {BORDER_COLOR};">
          <tr>
            <td style="background-color:{BRAND_BLUE}; padding:24px 32px;">
              <span style="font-family: Manrope, sans-serif; font-size:20px; font-weight:700; color:#ffffff; letter-spacing:0.02em;">QAPIShield</span>
            </td>
          </tr>
          <tr>
            <td style="height:3px; background-color:{BRAND_GOLD}; font-size:0; line-height:0;">&nbsp;</td>
          </tr>
          <tr>
            <td style="padding:32px;">
              <h1 style="margin:0 0 16px 0; font-family: Manrope, sans-serif; font-size:20px; font-weight:700; color:{BRAND_BLUE};">{heading}</h1>
              {paragraphs_html}
              <table role="presentation" cellpadding="0" cellspacing="0" style="margin:8px 0 24px 0;">
                <tr>
                  <td style="border-radius:6px; background-color:{BRAND_BLUE};">
                    <a href="{cta_link}" style="display:inline-block; padding:12px 28px; font-size:15px; font-weight:600; color:#ffffff; text-decoration:none; border-radius:6px;">{cta_text}</a>
                  </td>
                </tr>
              </table>
              <p style="margin:0; font-size:13px; color:{MUTED_TEXT};">{footer_note}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:20px 32px; background-color:{FOOTER_BG}; border-top:1px solid {BORDER_COLOR};">
              <p style="margin:0; font-size:12px; color:#9ca3af;">QAPIShield &middot; AI-powered QAPI software for skilled nursing facilities</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def send_email(to_email: str, subject: str, text_body: str, html_body: str = None) -> None:
    if not settings.SMTP_HOST:
        raise RuntimeError("SMTP_HOST is not configured — set SMTP_* settings before sending email")

    if html_body:
        message = MIMEMultipart("alternative")
        message.attach(MIMEText(text_body, "plain"))
        message.attach(MIMEText(html_body, "html"))
    else:
        message = MIMEText(text_body)

    message["Subject"] = subject
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = to_email

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        if settings.SMTP_USE_TLS:
            server.starttls()
        if settings.SMTP_USERNAME:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], message.as_string())


def send_verification_email(to_email: str, verification_link: str) -> None:
    send_email(
        to_email,
        subject="Verify your QAPIShield email address",
        text_body=(
            "Welcome to QAPIShield. Please verify your email address by clicking the link below:\n\n"
            f"{verification_link}\n\n"
            "This link expires in 72 hours."
        ),
        html_body=_render_html_email(
            heading="Verify your email address",
            paragraphs=[
                "Welcome to QAPIShield. Please confirm your email address to activate your account.",
            ],
            cta_text="Verify email",
            cta_link=verification_link,
            footer_note="This link expires in 72 hours. If you didn't create a QAPIShield account, you can ignore this email.",
        ),
    )


def send_verification_reminder_email(to_email: str, verification_link: str) -> None:
    send_email(
        to_email,
        subject="Reminder: verify your QAPIShield email address",
        text_body=(
            "You haven't verified your QAPIShield account yet. Please verify your email address "
            "by clicking the link below:\n\n"
            f"{verification_link}\n\n"
            "This link will expire soon — verify now to keep access to your account."
        ),
        html_body=_render_html_email(
            heading="Don't lose access to your account",
            paragraphs=[
                "You haven't verified your QAPIShield account yet. Verify now to keep access.",
            ],
            cta_text="Verify email",
            cta_link=verification_link,
            footer_note="This link will expire soon.",
        ),
    )


def build_verification_link(token: str) -> str:
    return f"{settings.FRONTEND_VERIFY_EMAIL_URL}?token={token}"


def build_password_reset_link(token: str) -> str:
    return f"{settings.FRONTEND_RESET_PASSWORD_URL}?token={token}"


def build_invite_link(token: str) -> str:
    return f"{settings.FRONTEND_ACCEPT_INVITE_URL}?token={token}"


def send_password_reset_email(to_email: str, reset_link: str) -> None:
    send_email(
        to_email,
        subject="Reset your QAPIShield password",
        text_body=(
            "We received a request to reset your QAPIShield password. Click the link below to "
            "choose a new password:\n\n"
            f"{reset_link}\n\n"
            "This link expires in 1 hour. If you didn't request this, you can ignore this email."
        ),
        html_body=_render_html_email(
            heading="Reset your password",
            paragraphs=[
                "We received a request to reset your QAPIShield password. Click below to choose a new one.",
            ],
            cta_text="Reset password",
            cta_link=reset_link,
            footer_note="This link expires in 1 hour. If you didn't request this, you can ignore this email.",
        ),
    )


def send_staff_invite_email(to_email: str, invite_link: str) -> None:
    send_email(
        to_email,
        subject="You've been invited to QAPIShield",
        text_body=(
            "You've been invited to join your facility's QAPIShield account. Click the link below "
            "to set your password and activate your account:\n\n"
            f"{invite_link}\n\n"
            "This link expires in 24 hours."
        ),
        html_body=_render_html_email(
            heading="You've been invited to QAPIShield",
            paragraphs=[
                "You've been invited to join your facility's QAPIShield account. Set your password to activate it.",
            ],
            cta_text="Accept invite",
            cta_link=invite_link,
            footer_note="This link expires in 24 hours.",
        ),
    )

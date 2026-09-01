"""
Application configuration using environment variables
"""
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "QAPIShield"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173", "https://app.qapishield.com"]

    # Used to build links in verification/password-reset emails
    APP_BASE_URL: str = "http://localhost:8000"

    # Frontend page URLs the token-based emails link to (frontend reads the
    # token from the query string and calls the corresponding backend API)
    FRONTEND_VERIFY_EMAIL_URL: str = "http://localhost:3000/verify-email"
    FRONTEND_RESET_PASSWORD_URL: str = "http://localhost:3000/reset-password"
    FRONTEND_ACCEPT_INVITE_URL: str = "http://localhost:3000/accept-invite"

    # Rate limits (slowapi format: "<count>/<period>", e.g. "5/minute")
    LOGIN_RATE_LIMIT: str = "5/minute"
    REGISTER_RATE_LIMIT: str = "1/hour"

    # Public self-service signup (creates a new facility + admin). Off by
    # default — sales-assisted onboarding is the default flow; flip on only
    # for environments that still need open registration.
    PUBLIC_REGISTRATION_ENABLED: bool = False

    # Account lockout after repeated failed login attempts
    LOGIN_LOCKOUT_THRESHOLD: int = 3
    LOGIN_LOCKOUT_DURATION_MINUTES: int = 15

    # Token link expiry (hours)
    VERIFICATION_LINK_EXPIRES_HOURS: int = 72
    PASSWORD_RESET_EXPIRES_HOURS: int = 1
    STAFF_INVITE_EXPIRES_HOURS: int = 24

    # SMTP / Email
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_USE_TLS: bool = True

    # Stripe billing
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    FRONTEND_BILLING_SUCCESS_URL: str = "http://localhost:3000/billing/success"
    FRONTEND_BILLING_CANCEL_URL: str = "http://localhost:3000/billing/cancel"
    FRONTEND_BILLING_PORTAL_RETURN_URL: str = "http://localhost:3000/billing"

    # Sentry error monitoring
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "development"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0

    class Config:
        env_file = ".env.local"  # Use .env.local for local development
        case_sensitive = True

settings = Settings()

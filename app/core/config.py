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

    # Token link expiry (hours)
    VERIFICATION_LINK_EXPIRES_HOURS: int = 72
    PASSWORD_RESET_EXPIRES_HOURS: int = 1
    STAFF_INVITE_EXPIRES_HOURS: int = 24

    # SMTP / Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = "devdab.contact@gmail.com"
    SMTP_PASSWORD: str = "gggxhkbrcqosrmdm"
    SMTP_FROM_EMAIL: str = "devdab.contact@gmail.com"
    SMTP_USE_TLS: bool = True

    class Config:
        env_file = ".env.local"  # Use .env.local for local development
        case_sensitive = True

settings = Settings()

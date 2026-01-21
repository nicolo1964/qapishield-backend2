import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool

# Get the database URL from environment variables
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# Fix for SQLAlchemy 2.0 + Psycopg 3:
# We must ensure the prefix is 'postgresql+psycopg://'
if SQLALCHEMY_DATABASE_URL:
    if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
    elif SQLALCHEMY_DATABASE_URL.startswith("postgresql://"):
        SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Create the engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    poolclass=NullPool if os.getenv("RENDER") else None
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

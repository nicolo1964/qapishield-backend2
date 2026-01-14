"""
Database connection and session management
"""

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Force SQLAlchemy to use psycopg v3
db_url = make_url(settings.DATABASE_URL)
db_url = db_url.set(drivername="postgresql+psycopg")

engine = create_engine(db_url)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


    autocommit=False,
    autoflush=False,
    bind=engine
)


Base = declarative_base()

def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

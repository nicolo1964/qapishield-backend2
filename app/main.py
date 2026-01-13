"""
QAPIShield Backend API
FastAPI application with PostgreSQL, JWT auth, and multi-tenant architecture
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1 import auth, facilities, residents, assessments, qapi

app = FastAPI(
    title="QAPIShield API",
    description="QAPI and Compliance Management System for Skilled Nursing Facilities",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(facilities.router, prefix="/api/v1/facilities", tags=["Facilities"])
app.include_router(residents.router, prefix="/api/v1/residents", tags=["Residents"])
app.include_router(assessments.router, prefix="/api/v1/assessments", tags=["Assessments"])
app.include_router(qapi.router, prefix="/api/v1/qapi", tags=["QAPI Dashboard"])

@app.get("/")
async def root():
    return {
        "message": "QAPIShield API",
        "version": "1.0.0",
        "docs": "/api/docs"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

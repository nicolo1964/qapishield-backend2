import uuid
import sentry_sdk
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from app.api.v1 import auth, facilities, residents, assessments, qapi, billing, platform
from app.core.database import engine, Base
from app.core.rate_limit import limiter
from app.core.scheduler import scheduler
from app.core.config import settings
from app.core.sentry import init_sentry

init_sentry()

# Create database tables on startup
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(
    title="QAPIShield API",
    version="1.0.0",
    docs_url="/docs",
redoc_url="/redoc",
openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    response = JSONResponse(
        status_code=429,
        content={"detail": "You've made too many attempts. Please try again in a while."},
    )
    return limiter._inject_headers(response, request.state.view_rate_limit)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    sentry_sdk.set_tag("request_id", request.state.request_id)
    return await call_next(request)

# Include Routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(facilities.router, prefix="/api/v1/facilities", tags=["Facilities"])
app.include_router(residents.router, prefix="/api/v1/residents", tags=["Residents"])
app.include_router(assessments.router, prefix="/api/v1/assessments", tags=["Assessments"])
app.include_router(qapi.router, prefix="/api/v1/qapi", tags=["QAPI"])
app.include_router(billing.router, prefix="/api/v1/billing", tags=["Billing"])
# Operator-only facility provisioning. include_in_schema=False keeps this
# entirely out of /docs, /redoc, and /openapi.json -- it is not a public
# customer-registration feature and must never be discoverable there.
app.include_router(
    platform.router, prefix="/api/v1/platform", tags=["Platform (internal)"],
    include_in_schema=False,
)

@app.get("/")
async def root():
    return {"message": "QAPIShield Backend API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

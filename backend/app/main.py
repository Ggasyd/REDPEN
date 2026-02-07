"""FastAPI application main entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.database import init_db
from app.schemas.common import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print("🚀 Starting REDPEN API...")
    # Note: Database tables will be created via Alembic migrations
    # await init_db()  # Uncomment for dev without Alembic
    print("✅ REDPEN API started successfully")
    yield
    # Shutdown
    print("👋 Shutting down REDPEN API...")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-Assisted Exam Correction SaaS Backend",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", version=settings.app_version)


# Import and include routers
from app.api import auth, workspaces, classrooms, exams, submissions, review, gdpr, ml_datasets

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(workspaces.router, prefix="/api/workspaces", tags=["Workspaces"])
app.include_router(classrooms.router, prefix="/api/classrooms", tags=["Classrooms"])
app.include_router(exams.router, prefix="/api/exams", tags=["Exams"])
app.include_router(submissions.router, prefix="/api/submissions", tags=["Submissions"])
app.include_router(review.router, prefix="/api/review", tags=["Review"])
app.include_router(gdpr.router, prefix="/api/gdpr", tags=["GDPR"])
app.include_router(ml_datasets.router, prefix="/api/ml", tags=["ML Datasets"])


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }

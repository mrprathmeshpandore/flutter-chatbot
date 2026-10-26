import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.database import init_db
from app.routers import auth, pdf, learning_path, ai, quiz, progress

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mindvault_ai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context:
    Runs startup actions (e.g. database table creation) and teardown.
    """
    logger.info("Starting MindVault AI Backend...")
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.warning(
            f"Could not connect to database on startup ({e}). "
            "If using PostgreSQL, ensure it is running and credentials in .env are correct."
        )
    yield
    logger.info("Shutting down MindVault AI Backend...")


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Backend API for MindVault AI — Personal AI Teacher. "
        "Provides authentication, PDF processing, AI tutoring grounded in document content, "
        "personalized learning paths, quiz generation, and progress tracking."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

from app.services.ai_service import AIServiceError

# Configure CORS for Flutter frontend (Web, Mobile, Desktop)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Specific Exception Handler for Gemini / AI Service Errors
@app.exception_handler(AIServiceError)
async def ai_service_exception_handler(request: Request, exc: AIServiceError):
    logger.error(
        f"AI service error on {request.method} {request.url.path} (status={exc.status_code}): {exc.message}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


# Global Exception Handler to safeguard against leaking stack traces or internal secrets
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."},
    )


# Include Routers
app.include_router(auth.router)
app.include_router(pdf.router)
app.include_router(learning_path.router)
app.include_router(ai.router)
app.include_router(quiz.router)
app.include_router(progress.router)


@app.get("/", tags=["Health"])
def health_check():
    """
    API Health check and welcome endpoint.
    """
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "docs_url": "/docs",
    }

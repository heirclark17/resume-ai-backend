from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import init_db
from app.routes import resumes, tailoring, auth
from app.utils.logger import logger

settings = get_settings()

app = FastAPI(title=settings.app_name, version=settings.app_version)

# CORS - Explicit origins for security
allowed_origins = [origin.strip() for origin in settings.allowed_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Explicit origins from config
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
)

# Startup: Initialize database
@app.on_event("startup")
async def startup_event():
    logger.info("Starting ResumeAI Backend...")
    await init_db()
    logger.info(f"Backend ready at http://{settings.backend_host}:{settings.backend_port}")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": settings.app_version,
        "message": "ResumeAI Backend is running"
    }

# Root endpoint
@app.get("/")
async def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "status": "running"
    }

# Request logging middleware
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"{request.method} {request.url.path}")

    # Sanitize headers before logging (remove sensitive data)
    if logger.level <= 10:  # DEBUG level
        sanitized_headers = {
            k: v if k.lower() not in ['x-api-key', 'authorization', 'cookie'] else '***REDACTED***'
            for k, v in request.headers.items()
        }
        logger.debug(f"Headers: {sanitized_headers}")

    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response

# Register routes
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(resumes.router, prefix="/api/resumes", tags=["Resumes"])
app.include_router(tailoring.router, prefix="/api/tailor", tags=["Tailoring"])

# Railway deployment - use railway.json startCommand instead
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",  # Fixed: removed 'backend.' prefix
        host=settings.backend_host,
        port=settings.backend_port,
        reload=settings.debug
    )

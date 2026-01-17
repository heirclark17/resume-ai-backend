from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.config import get_settings
from app.database import init_db
from app.routes import resumes, tailoring, auth, admin, interview_prep, star_stories, resume_analysis, certifications, saved_comparisons, jobs, career_path
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.waf import WAFMiddleware
from app.utils.logger import logger

settings = get_settings()

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title=settings.app_name, version=settings.app_version)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Web Application Firewall - Block malicious requests
app.add_middleware(WAFMiddleware)

# Security Headers - CSP, HSTS, X-Frame-Options, etc.
app.add_middleware(SecurityHeadersMiddleware)

# CORS - Explicit origins for security (MUST be added LAST so it runs FIRST)
allowed_origins = [origin.strip() for origin in settings.allowed_origins.split(",")]
logger.info(f"CORS allowed origins: {allowed_origins}")
logger.info(f"Raw ALLOWED_ORIGINS env var: {settings.allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Explicit origins from config
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization", "X-TOTP-Code", "X-User-ID"],
    expose_headers=["*"],
    max_age=3600,
)

# Startup: Initialize database
@app.on_event("startup")
async def startup_event():
    logger.info("Starting ResumeAI Backend...")
    await init_db()
    logger.info(f"Backend ready at http://{settings.backend_host}:{settings.backend_port}")

# Health check endpoint (minimal response to prevent information disclosure)
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Root endpoint (minimal response to prevent information disclosure)
@app.get("/")
async def root():
    return {"status": "ok"}

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
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(tailoring.router, prefix="/api/tailor", tags=["Tailoring"])
app.include_router(interview_prep.router)  # Prefix already in router definition
app.include_router(star_stories.router)  # Prefix already in router definition
app.include_router(resume_analysis.router, prefix="/api/resume-analysis", tags=["Resume Analysis"])
app.include_router(certifications.router, prefix="/api/certifications", tags=["Certifications"])
app.include_router(saved_comparisons.router, prefix="/api/saved-comparisons", tags=["Saved Comparisons"])
app.include_router(career_path.router)  # Prefix already in router definition
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])

# Railway deployment - use railway.json startCommand instead
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",  # Fixed: removed 'backend.' prefix
        host=settings.backend_host,
        port=settings.backend_port,
        reload=settings.debug
    )

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import init_db
from app.routes import resumes, tailoring, auth

settings = get_settings()

app = FastAPI(title=settings.app_name, version=settings.app_version)

# CORS - Allow Electron renderer to communicate
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local Electron app
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup: Initialize database
@app.on_event("startup")
async def startup_event():
    print("Starting ResumeAI Backend...")
    await init_db()
    print(f"Backend ready at http://{settings.backend_host}:{settings.backend_port}")

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
    print(f"Incoming request: {request.method} {request.url.path}")
    print(f"Headers: {dict(request.headers)}")
    response = await call_next(request)
    print(f"Response status: {response.status_code}")
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

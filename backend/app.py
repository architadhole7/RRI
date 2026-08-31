import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.logging_config import setup_logging
from backend.routers import analytics, audit, health, payments, recovery, security

setup_logging(settings.log_level)

logger = logging.getLogger("revenueguard")

app = FastAPI(
    title=settings.app_name,
    description="AI-Powered Revenue Recovery Decision & Orchestration Agent",
    version=settings.app_version,
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception processing request '%s': %s", request.url.path, str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An error occurred while processing your request safely.",
        },
    )


# Register modular API routers
app.include_router(health.router)
app.include_router(payments.router)
app.include_router(recovery.router)
app.include_router(security.router)
app.include_router(analytics.router)
app.include_router(audit.router)

# Mount Dashboard Frontend (Strictly scoped to frontend/dashboard directory)
dashboard_path = Path("frontend/dashboard")
if dashboard_path.exists():
    app.mount("/dashboard", StaticFiles(directory=str(dashboard_path), html=True), name="dashboard")


@app.get("/")
def root():
    logger.info("Root endpoint accessed")
    return {
        "message": "RevenueGuard API is running",
        "docs_url": "/docs",
        "dashboard_url": "/dashboard",
    }
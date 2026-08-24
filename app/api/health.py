"""Liveness and readiness routes."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.health import HealthCheckService


def create_health_router(service: HealthCheckService) -> APIRouter:
    """Create health routes backed by the provided service."""
    router = APIRouter(tags=["health"])

    @router.get("/health/live")
    async def liveness() -> dict[str, str]:
        """Report whether the web process can serve requests."""
        return {"status": "alive"}

    @router.get("/health/ready")
    async def readiness() -> JSONResponse:
        """Report whether every required runtime dependency is available."""
        report = await service.readiness()
        status_code = 200 if report.is_ready else 503
        return JSONResponse(content=report.as_dict(), status_code=status_code)

    return router

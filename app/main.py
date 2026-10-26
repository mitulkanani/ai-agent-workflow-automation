from fastapi import FastAPI

from app.api.routes import router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "A demo of guarded agent workflows: allowlisted tools, validated inputs, "
        "explicit approval gates, and execution traces."
    ),
)
app.include_router(router)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    """Return a small discovery document."""
    return {
        "name": settings.app_name,
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
    }

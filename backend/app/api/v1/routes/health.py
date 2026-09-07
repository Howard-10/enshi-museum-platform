from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Lightweight endpoint for local checks and container orchestration."""

    return {"status": "ok", "service": "enshi-museum-backend"}

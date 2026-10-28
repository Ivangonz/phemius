from fastapi import APIRouter

from phemius.services.health import check_health

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    check_health()
    return {"status": "ok"}

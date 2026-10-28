from fastapi import APIRouter

from phemius.services.library_config import LibraryConfig, describe_library

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
def library_config() -> LibraryConfig:
    return describe_library()

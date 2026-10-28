from fastapi import APIRouter

from phemius.config import Settings
from phemius.services import settings as settings_service
from phemius.services.settings import SettingsOverview

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings")
def get_settings() -> SettingsOverview:
    return settings_service.describe_settings()


@router.patch("/settings")
def update_settings(update: Settings) -> SettingsOverview:
    """Partial update: only the fields sent are saved; `null` clears a saved value."""
    settings_service.update_settings(update)
    return settings_service.describe_settings()

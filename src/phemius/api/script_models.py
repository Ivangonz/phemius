from fastapi import APIRouter

from phemius.services import script_models
from phemius.services.script_models import OllamaModelList, ScriptModelConnection

router = APIRouter(prefix="/api/models", tags=["models"])


# Plain `def` routes run in the thread pool: both calls wait on a provider.
@router.get("/ollama")
def list_ollama_models() -> OllamaModelList:
    """Models installed in the saved Ollama server, sorted by name."""
    return script_models.list_ollama_models()


@router.post("/check")
def check_script_model() -> ScriptModelConnection:
    """Test the saved script model: latency when it answers, else error and hint."""
    return script_models.check_connection()

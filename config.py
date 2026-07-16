import os

from dotenv import load_dotenv
from openai import OpenAI

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def load_settings() -> tuple[str, str]:
    """Load API key and model from the environment (.env). Raises if either is missing."""
    load_dotenv()
    api_key = os.getenv("API_KEY")
    model = os.getenv("MODEL")
    if not api_key or not model:
        raise ValueError("API_KEY or MODEL not found — check your .env file")
    return api_key, model


def create_client() -> tuple[OpenAI, str]:
    """Return a configured OpenRouter client and the model name. Raises if unconfigured.

    Single source of truth for LLM access, shared by the CLI and the UI.
    """
    api_key, model = load_settings()
    return OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL), model


def web_search_enabled_default() -> bool:
    """Default web-search setting from ENABLE_WEB_SEARCH (off unless explicitly enabled)."""
    load_dotenv()
    return os.getenv("ENABLE_WEB_SEARCH", "false").strip().lower() in ("1", "true", "yes")

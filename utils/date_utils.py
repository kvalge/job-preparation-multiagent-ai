from datetime import date


def get_today() -> str:
    """Return today's date as an ISO string (e.g. '2026-07-11'), for injecting into prompts."""
    return date.today().isoformat()
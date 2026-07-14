from datetime import date


def get_today() -> str:
    """Return today's date as an ISO string (e.g. '2026-07-11'), for injecting into prompts."""
    return date.today().isoformat()


def days_until(deadline: str | None, default_days: int = 7) -> int:
    """Return the number of days from today until an ISO deadline string.

    Falls back to default_days when the deadline is missing or unparseable.
    Past deadlines clamp to 0.
    """
    if not deadline:
        return default_days
    try:
        target = date.fromisoformat(deadline)
    except ValueError:
        return default_days
    return max((target - date.today()).days, 0)
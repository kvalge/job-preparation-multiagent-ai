import os

CV_PATH = "data/cv.txt"


def load_cv(path: str = CV_PATH) -> str | None:
    """Return stored CV text, or None if none exists yet."""
    if os.path.exists(path):
        content = open(path, "r", encoding="utf-8").read().strip()
        return content or None
    return None


def save_cv(text: str, path: str = CV_PATH) -> None:
    text = text.strip()
    if not text:
        raise ValueError("CV text cannot be empty.")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
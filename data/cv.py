import os

CV_PATH = "data/cv.txt"
CV_REVISIONS_DIR = "data/cv_revisions"


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


def save_revised_cv(
    text: str, job_post_id: int, dir_path: str = CV_REVISIONS_DIR
) -> str:
    """Write a job-tailored revised CV to its own file and return the path.

    Saved separately from the original data/cv.txt (never overwritten) as markdown,
    so a front-end can render it and offer a download / PDF export.
    """
    text = text.strip()
    if not text:
        raise ValueError("Revised CV text cannot be empty.")
    os.makedirs(dir_path, exist_ok=True)
    path = os.path.join(dir_path, f"cv_{job_post_id}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path
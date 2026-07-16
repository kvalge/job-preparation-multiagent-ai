import os
import re

JOB_POST_PATH = "data/job_post.txt"
JOB_POSTS_DIR = "data/job_posts"


def load_job_post(path: str = JOB_POST_PATH) -> str | None:
    if os.path.exists(path):
        content = open(path, "r", encoding="utf-8").read().strip()
        return content or None
    return None


def save_job_post(text: str, path: str = JOB_POST_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text.strip())


def _slugify(value: str | None) -> str:
    """Turn a company/title into a filesystem-safe slug (fallback: 'unknown')."""
    slug = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")
    return slug or "unknown"


def save_job_post_file(
    text: str,
    company: str | None,
    job_title: str | None,
    date_saved: str,
    unique_suffix: str,
    dir_path: str = JOB_POSTS_DIR,
) -> str:
    """Archive a saved job post to its own named file and return the path.

    Named job_post_<company>_<title>_<date>_<suffix>.txt so multiple posts are easy to
    tell apart; the suffix (a short content hash) keeps filenames unique when company,
    title and date collide.
    """
    os.makedirs(dir_path, exist_ok=True)
    filename = (
        f"job_post_{_slugify(company)}_{_slugify(job_title)}_"
        f"{date_saved}_{unique_suffix}.txt"
    )
    path = os.path.join(dir_path, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text.strip())
    return path

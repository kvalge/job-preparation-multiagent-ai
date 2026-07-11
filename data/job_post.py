import os

JOB_POST_PATH = "data/job_post.txt"


def load_job_post(path: str = JOB_POST_PATH) -> str | None:
    if os.path.exists(path):
        content = open(path, "r", encoding="utf-8").read().strip()
        return content or None
    return None


def save_job_post(text: str, path: str = JOB_POST_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text.strip())
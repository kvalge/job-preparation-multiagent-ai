import os

MOTIVATION_LETTERS_DIR = "data/motivation_letters"


def save_motivation_letter(
    text: str, job_post_id: int, dir_path: str = MOTIVATION_LETTERS_DIR
) -> str:
    """Write a motivation letter to its own markdown file and return the path."""
    text = text.strip()
    if not text:
        raise ValueError("Motivation letter text cannot be empty.")
    os.makedirs(dir_path, exist_ok=True)
    path = os.path.join(dir_path, f"motivation_letter_{job_post_id}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path

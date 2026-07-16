import os

MOTIVATION_LETTERS_DIR = "data/motivation_letters"


def save_motivation_letter(
    text: str, name_stem: str, dir_path: str = MOTIVATION_LETTERS_DIR
) -> str:
    """Write a motivation letter to its own markdown file and return its path.

    name_stem is the shared <company>_<title>_<date>_id<postid> stem.
    """
    text = text.strip()
    if not text:
        raise ValueError("Motivation letter text cannot be empty.")
    os.makedirs(dir_path, exist_ok=True)
    path = os.path.join(dir_path, f"motivation_letter_{name_stem}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path

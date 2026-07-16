import json
import os

LEARNING_PLANS_DIR = "data/learning_plans"


def save_learning_plan(
    plan: dict, name_stem: str, dir_path: str = LEARNING_PLANS_DIR
) -> str:
    """Write a learning plan to a JSON file and return its path.

    JSON is used so a front-end can render it and offer a download (or convert it to
    Markdown / PDF / calendar) without re-parsing. name_stem is the shared
    <company>_<title>_<date>_id<postid> stem.
    """
    os.makedirs(dir_path, exist_ok=True)
    path = os.path.join(dir_path, f"learning_plan_{name_stem}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
    return path

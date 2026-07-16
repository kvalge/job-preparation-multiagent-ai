import json

from openai import OpenAI

from agents.job_ranking import rank_job_posts
from data.db import get_latest_ranking, list_analyzed_job_posts, save_ranking


def _build_job_inputs() -> list[dict]:
    """Flatten each analyzed job post + its stored summary into a ranking input row."""
    jobs: list[dict] = []
    for post in list_analyzed_job_posts():
        try:
            summary = json.loads(post.get("analysis_summary") or "{}")
        except json.JSONDecodeError:
            summary = {}
        jobs.append(
            {
                "job_post_id": post["id"],
                "company": post.get("company"),
                "job_title": post.get("job_title"),
                "deadline": post.get("job_post_deadline"),
                "status": post.get("status"),
                "verdict": summary.get("verdict") or post.get("match_verdict"),
                "days_remaining": summary.get("days_remaining"),
                "gap_count": summary.get("gap_count"),
                "top_gaps": summary.get("top_gaps"),
                "plan_realistic": summary.get("plan_realistic"),
                "plan_total_days": summary.get("plan_total_days"),
            }
        )
    return jobs


def refresh_ranking(client: OpenAI, model: str) -> dict | None:
    """Re-rank every analyzed job post, persist the result, and return it.

    Returns None when there is nothing to rank yet.
    """
    jobs = _build_job_inputs()
    if not jobs:
        return None

    ranking = rank_job_posts(client, model, jobs)
    save_ranking(json.dumps(ranking))
    return ranking


def load_latest_ranking() -> dict | None:
    """Return the most recently stored ranking as a dict, or None."""
    row = get_latest_ranking()
    if not row or not row.get("content"):
        return None
    try:
        ranking = json.loads(row["content"])
    except json.JSONDecodeError:
        return None
    ranking["created_at"] = row.get("created_at")
    return ranking

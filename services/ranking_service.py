import json

from openai import OpenAI

from agents.job_ranking import rank_job_posts
from data.db import get_latest_ranking, list_analyzed_job_posts, save_ranking

_VERDICT_SCORE = {"good_fit": 3, "stretch_fit": 2, "poor_fit": 1}


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


def _job_sort_key(job: dict) -> tuple:
    """Higher is better for ranking: fit, realistic plan, fewer gaps, sooner deadline."""
    verdict = _VERDICT_SCORE.get(str(job.get("verdict") or ""), 0)
    realistic = 1 if job.get("plan_realistic") else 0
    status_ok = 0 if job.get("status") == "declined" else 1
    gaps = job.get("gap_count")
    gap_score = -(gaps if isinstance(gaps, int) else 99)
    days = job.get("days_remaining")
    # Prefer some urgency, but not expired (0) when plan needs time.
    day_score = -(days if isinstance(days, int) else 999)
    return (status_ok, verdict, realistic, gap_score, day_score)


def deterministic_rank(jobs: list[dict]) -> dict:
    """Rule-based ranking used when the LLM ranking call fails or returns junk."""
    ordered = sorted(jobs, key=_job_sort_key, reverse=True)
    ranking_rows = []
    for i, job in enumerate(ordered, start=1):
        pid = job["job_post_id"]
        label = " — ".join(
            p for p in (job.get("company"), job.get("job_title")) if p
        ) or f"#{pid}"
        verdict = job.get("verdict") or "unknown"
        if job.get("status") == "declined":
            rec = "skip"
        elif verdict == "good_fit" and job.get("plan_realistic") is not False:
            rec = "pursue"
        elif verdict == "poor_fit":
            rec = "skip"
        else:
            rec = "maybe"
        ranking_rows.append(
            {
                "job_post_id": pid,
                "rank": i,
                "recommendation": rec,
                "reason": (
                    f"{label}: {verdict}, "
                    f"{job.get('gap_count', '?')} gaps, "
                    f"plan_realistic={job.get('plan_realistic')}, "
                    f"{job.get('days_remaining', '?')} days left."
                ),
            }
        )
    top = ordered[0] if ordered else {}
    top_id = top.get("job_post_id")
    return {
        "ranking": ranking_rows,
        "top_pick": {
            "job_post_id": top_id,
            "why": (
                f"Ranked {len(jobs)} analyzed job(s) with a rule-based fallback "
                "(LLM ranking unavailable). Prefer stronger fit and a realistic plan."
            ),
        },
        "overall_note": (
            f"Compared {len(jobs)} analyzed job post(s). "
            "This ranking used a deterministic fallback because the ranking model call failed."
        ),
        "_fallback": True,
    }


def _normalize_ranking(ranking: dict, jobs: list[dict]) -> dict:
    """Ensure every analyzed job appears once; fill gaps with a deterministic order."""
    expected_ids = {j["job_post_id"] for j in jobs}
    rows = list(ranking.get("ranking") or [])
    seen = set()
    cleaned = []
    for row in rows:
        pid = row.get("job_post_id")
        if pid in expected_ids and pid not in seen:
            seen.add(pid)
            cleaned.append(row)

    if seen != expected_ids:
        # Rebuild fully from deterministic order, preserving any LLM reasons we have.
        reasons = {r.get("job_post_id"): r for r in cleaned}
        fallback = deterministic_rank(jobs)
        merged = []
        for row in fallback["ranking"]:
            pid = row["job_post_id"]
            if pid in reasons:
                merged.append(reasons[pid])
            else:
                merged.append(row)
        # Re-number ranks
        for i, row in enumerate(merged, start=1):
            row["rank"] = i
        ranking = {
            "ranking": merged,
            "top_pick": ranking.get("top_pick") or fallback["top_pick"],
            "overall_note": (
                (ranking.get("overall_note") or "")
                + f" (Normalized to include all {len(jobs)} analyzed jobs.)"
            ).strip(),
        }
        top = ranking.get("top_pick") or {}
        if top.get("job_post_id") not in expected_ids and merged:
            ranking["top_pick"] = {
                "job_post_id": merged[0]["job_post_id"],
                "why": merged[0].get("reason") or fallback["top_pick"]["why"],
            }
    else:
        ranking["ranking"] = cleaned
        # Ensure ranks are 1..n
        for i, row in enumerate(cleaned, start=1):
            row["rank"] = i

    return ranking


def refresh_ranking(client: OpenAI, model: str) -> dict | None:
    """Re-rank every analyzed job post with the given model and persist the result.

    Raises on LLM failure so the pipeline can retry / switch to FALLBACK_MODEL.
    """
    jobs = _build_job_inputs()
    if not jobs:
        return None

    print(f"[ranking] Ranking {len(jobs)} analyzed job post(s) with model={model}...")
    ranking = rank_job_posts(client, model, jobs)
    ranking = _normalize_ranking(ranking, jobs)
    ranking["jobs_ranked"] = len(jobs)
    save_ranking(json.dumps(ranking))
    return ranking


def save_deterministic_ranking() -> dict | None:
    """Persist a rule-based ranking of all analyzed posts (last resort)."""
    jobs = _build_job_inputs()
    if not jobs:
        return None
    print(
        f"  (Using deterministic ranking fallback for {len(jobs)} analyzed job post(s).)"
    )
    ranking = deterministic_rank(jobs)
    ranking["jobs_ranked"] = len(jobs)
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

    analyzed = list_analyzed_job_posts()
    analyzed_ids = {p["id"] for p in analyzed}
    ranked_ids = {
        row.get("job_post_id") for row in (ranking.get("ranking") or [])
    }
    ranking["analyzed_count"] = len(analyzed_ids)
    ranking["ranked_count"] = len(ranked_ids & analyzed_ids)
    ranking["stale"] = bool(analyzed_ids) and ranked_ids != analyzed_ids
    return ranking

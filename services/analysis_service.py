import os

from openai import OpenAI

from agents.cv_advisor_agent import advise_cv
from agents.gap_analysis import analyze_gaps
from agents.learning_plan import create_learning_plan
from agents.match_check import check_fit
from agents.motivation_letter_agent import create_motivation_letter
from data.cv import save_revised_cv
from data.db import get_job_post, update_job_post_analysis
from data.learning_plan import save_learning_plan
from data.motivation_letter import save_motivation_letter
from utils.date_utils import days_until, get_today
from utils.pipeline import run_stage
from utils.text_utils import output_stem


def load_saved_job_post_text(job_post_id: int) -> str:
    """Read the archived raw text of a saved job post from its txt_path."""
    post = get_job_post(job_post_id)
    if post is None:
        raise ValueError(f"Job post {job_post_id} not found.")
    txt_path = post.get("txt_path")
    if not txt_path or not os.path.exists(txt_path):
        raise ValueError(
            f"Archived text for job post {job_post_id} not found "
            f"(txt_path={txt_path!r})."
        )
    return open(txt_path, "r", encoding="utf-8").read().strip()


def run_analysis(
    client: OpenAI,
    model: str,
    job_post_id: int,
    cv: str,
    cv_version_id: int | None = None,
    *,
    use_web_search: bool = False,
    proceed_on_poor_fit: bool = True,
) -> dict:
    """Run the full analysis pipeline on a saved job post and return structured results.

    Stages: fit → (record) → gap → learning plan → CV advisor → motivation letter.
    Resilient: a failing stage is skipped, not fatal. Generated files are named with
    <company>_<title>_<date>_id<postid>. Returns a dict with each stage's result and the
    saved file paths.
    """
    post = get_job_post(job_post_id) or {}
    job_post = load_saved_job_post_text(job_post_id)
    results: dict = {"job_post_id": job_post_id, "cv_version_id": cv_version_id}

    print("[analysis] Evaluating fit...")
    fit = run_stage("Fit evaluation", check_fit, client, model, cv, job_post)
    results["fit"] = fit
    if fit is None:
        results["status"] = "error"
        return results

    verdict = fit.get("verdict")
    reasoning = fit.get("reasoning", "")

    if verdict == "poor_fit" and not proceed_on_poor_fit:
        print("[analysis] Poor fit — stopping (proceed_on_poor_fit is off).")
        run_stage(
            "Recording analysis",
            update_job_post_analysis,
            job_post_id, verdict, reasoning, "declined", cv_version_id,
        )
        results["status"] = "declined"
        return results

    run_stage(
        "Recording analysis",
        update_job_post_analysis,
        job_post_id, verdict, reasoning, "continued", cv_version_id,
    )
    results["status"] = "continued"

    date_saved = post.get("date_saved") or get_today()
    stem = output_stem(post.get("company"), post.get("job_title"), date_saved, job_post_id)

    days_remaining = days_until(post.get("job_post_deadline"))
    results["days_remaining"] = days_remaining

    print(f"[analysis] Gap analysis ({days_remaining} days until deadline)...")
    gaps = run_stage(
        "Gap analysis", analyze_gaps, client, model, cv, job_post, days_remaining
    )
    results["gaps"] = gaps

    if gaps is not None:
        print("[analysis] Building learning plan...")
        plan = run_stage(
            "Learning plan",
            create_learning_plan,
            client, model, gaps, days_remaining, use_web_search,
        )
        if plan is not None:
            results["plan"] = plan
            results["plan_path"] = save_learning_plan(plan, stem)

    print("[analysis] Tailoring CV...")
    advice = run_stage("CV tailoring", advise_cv, client, model, cv, job_post)
    if advice is not None:
        results["cv"] = advice
        results["cv_path"] = save_revised_cv(advice["revised_cv"], stem)

    print("[analysis] Writing motivation letter...")
    letter = run_stage(
        "Motivation letter", create_motivation_letter, client, model, cv, job_post
    )
    if letter is not None:
        results["letter"] = letter
        results["letter_path"] = save_motivation_letter(letter["motivation_letter"], stem)

    return results

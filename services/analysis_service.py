import json
import os

from openai import OpenAI

from agents.cv_advisor_agent import advise_cv
from agents.gap_analysis import analyze_gaps
from agents.learning_plan import create_learning_plan
from agents.match_check import check_fit
from agents.motivation_letter_agent import create_motivation_letter
from data.cv import save_revised_cv
from data.db import get_job_post, update_job_post_analysis, update_job_post_summary
from data.learning_plan import save_learning_plan
from data.motivation_letter import save_motivation_letter
from services.ranking_service import refresh_ranking, save_deterministic_ranking
from services.statistics_service import (
    DEFAULT_TOP_COMPANIES,
    DEFAULT_TOP_SKILLS,
    DEFAULT_TOP_TITLES,
    refresh_statistics,
)
from utils.analysis_log import log_stage_info, utc_now_iso
from utils.date_utils import days_until, get_today
from utils.pipeline import run_stage
from utils.text_utils import output_stem

# Ordered pipeline stages (resume starts at the named stage and continues forward).
STAGE_ORDER = [
    "fit",
    "gaps",
    "plan",
    "cv",
    "letter",
    "ranking",
    "statistics",
]

# Artifacts the pipeline aims to produce whenever the user proceeds past fit.
REQUIRED_OUTPUT_STAGES = ("plan", "cv", "letter")

STAGE_LABELS = {
    "fit": "Fit evaluation",
    "gaps": "Gap analysis",
    "plan": "Learning plan",
    "cv": "CV tailoring",
    "letter": "Motivation letter",
    "ranking": "Job ranking",
    "statistics": "Statistics",
}


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


def _stage_index(stage: str) -> int:
    try:
        return STAGE_ORDER.index(stage)
    except ValueError as e:
        raise ValueError(f"Unknown pipeline stage: {stage!r}") from e


def _should_run(stage: str, resume_from: str | None, results: dict) -> bool:
    """Decide whether to execute a stage on a fresh or resumed run.

    On resume: re-run the failed stage; re-run later required stages only if their
    output is still missing; always refresh ranking/statistics after a resume.
    """
    if resume_from is None:
        return True
    idx = _stage_index(stage)
    resume_idx = _stage_index(resume_from)
    if idx < resume_idx:
        return False
    if idx == resume_idx:
        return True
    # Later stages
    if stage == "gaps":
        return not results.get("gaps") or bool(results.get("gaps_fallback"))
    if stage == "plan":
        return not results.get("plan")
    if stage == "cv":
        return not results.get("cv")
    if stage == "letter":
        return not results.get("letter")
    if stage in ("ranking", "statistics"):
        return True
    return True


def _gaps_fallback_from_fit(fit: dict, days_remaining: int) -> dict:
    """Build a minimal gap analysis from the fit check so a learning plan can still run."""
    key_gaps = fit.get("key_gaps") or []
    if not key_gaps:
        key_gaps = ["role-specific requirements highlighted in the job post"]

    n = len(key_gaps)
    per_gap_days = max(1, days_remaining // n) if days_remaining > 0 else 1
    prioritized = []
    for i, gap in enumerate(key_gaps, start=1):
        skill = gap if isinstance(gap, str) else str(gap)
        prioritized.append(
            {
                "skill": skill,
                "importance": "important",
                "estimated_days_to_learn": per_gap_days,
                "achievable_before_deadline": True,
                "priority": i,
                "recommendation": (
                    f"Focus study time on {skill} using reputable free resources "
                    "relevant to this role."
                ),
            }
        )
    return {
        "skill_assessment": [],
        "prioritized_gaps": prioritized,
        "overall_summary": (
            "Full gap analysis was unavailable; this fallback uses the fit-check "
            "gaps so a learning plan, revised CV, and letter can still be produced."
        ),
        "_fallback": True,
    }


def _store_summary_and_rank(
    client: OpenAI,
    model: str,
    job_post_id: int,
    verdict: str | None,
    days_remaining: int | None,
    gaps: dict | None,
    plan: dict | None,
    failures: list[dict],
    fallback_model: str | None = None,
) -> dict | None:
    """Persist a compact analysis summary, then re-rank all analyzed job posts."""
    prioritized = (gaps or {}).get("prioritized_gaps") or []
    summary = {
        "verdict": verdict,
        "days_remaining": days_remaining,
        "gap_count": len(prioritized),
        "top_gaps": [g.get("skill") for g in prioritized[:5]],
        "plan_realistic": (plan or {}).get("realistic"),
        "plan_total_days": (plan or {}).get("total_estimated_days"),
        "plan_feasibility_note": (plan or {}).get("feasibility_note"),
    }
    run_stage(
        "Saving analysis summary",
        update_job_post_summary,
        job_post_id,
        json.dumps(summary),
        failures=failures,
        job_post_id=job_post_id,
        stage_key="summary",
        model_pos=None,
    )
    print("[analysis] Ranking job posts...")
    ranking = run_stage(
        "Ranking job posts",
        refresh_ranking,
        client,
        model,
        failures=failures,
        job_post_id=job_post_id,
        stage_key="ranking",
        fallback_model=fallback_model,
        model_pos=1,
    )
    if ranking is None:
        ranking = save_deterministic_ranking()
    return ranking


def _first_retry_stage(results: dict) -> str | None:
    """Earliest stage the user should retry.

    Prefer missing required outputs (plan / CV / letter). If those exist but gap
    analysis only succeeded via the fit-check fallback, offer a gaps retry so the
    user can still get a full gap analysis.
    """
    for stage in REQUIRED_OUTPUT_STAGES:
        if stage == "plan" and not results.get("plan"):
            # Prefer retrying gaps if those are also missing (plan depends on them).
            if not results.get("gaps"):
                return "gaps"
            return "plan"
        if stage == "cv" and not results.get("cv"):
            return "cv"
        if stage == "letter" and not results.get("letter"):
            return "letter"
    if results.get("gaps_fallback"):
        return "gaps"
    # Ranking missing or failed after a proceed run — allow resume from ranking.
    if results.get("status") == "continued" and not results.get("ranking"):
        return "ranking"
    return None


def _finalize_status(results: dict) -> None:
    """Set incomplete / retry_from / notification fields from failures and missing outputs."""
    retry_from = _first_retry_stage(results)
    results["retry_from"] = retry_from
    missing_required = any(
        not results.get(key) for key in ("plan", "cv", "letter")
    )
    ranking_missing = (
        results.get("status") == "continued" and not results.get("ranking")
    )
    results["incomplete"] = (
        missing_required
        or bool(results.get("gaps_fallback"))
        or ranking_missing
    )
    if retry_from:
        label = STAGE_LABELS.get(retry_from, retry_from)
        if retry_from == "ranking" and not missing_required:
            results["notification"] = (
                f"Cross-post ranking did not update. Click Retry from '{label}' so all "
                f"analyzed jobs are compared. See logs/analysis.log."
            )
        elif results.get("gaps_fallback") and not missing_required:
            results["notification"] = (
                f"Gap analysis used a fallback. Click Retry from '{label}' for a fuller "
                f"result (learning plan, CV, and letter were already created). "
                f"See logs/analysis.log."
            )
        else:
            results["notification"] = (
                f"Analysis incomplete: '{label}' did not finish successfully. "
                f"You can retry from that stage. Details are in logs/analysis.log."
            )
        log_stage_info(
            f"Analysis incomplete for job #{results.get('job_post_id')}; "
            f"retry_from={retry_from}"
        )
    else:
        results["notification"] = None
        if results.get("status") == "continued":
            log_stage_info(
                f"Analysis complete for job #{results.get('job_post_id')} "
                "(learning plan, revised CV, and motivation letter produced)."
            )


def run_analysis(
    client: OpenAI,
    model: str,
    job_post_id: int,
    cv: str,
    cv_version_id: int | None = None,
    *,
    use_web_search: bool = False,
    proceed_on_poor_fit: bool = True,
    top_companies: int = DEFAULT_TOP_COMPANIES,
    top_titles: int = DEFAULT_TOP_TITLES,
    top_skills: int = DEFAULT_TOP_SKILLS,
    fallback_model: str | None = None,
    resume_from: str | None = None,
    previous_results: dict | None = None,
) -> dict:
    """Run (or resume) the analysis pipeline on a saved job post.

    When the user proceeds past fit (including poor_fit with proceed_on_poor_fit=True),
    the pipeline always aims to produce a learning plan, revised CV, and motivation
    letter. Failed stages are logged and recorded; pass `resume_from` +
    `previous_results` to retry from the failed stage without redoing earlier work.

    LLM stages try primary model → primary retry → optional FALLBACK_MODEL.
    """
    if resume_from is not None:
        _stage_index(resume_from)  # validate

    # Prefer explicitly passed fallback; else keep one stored on a resumed run.
    if fallback_model is None and previous_results:
        fallback_model = previous_results.get("fallback_model")

    post = get_job_post(job_post_id) or {}
    job_post = load_saved_job_post_text(job_post_id)
    days_remaining = days_until(post.get("job_post_deadline"))

    results: dict = dict(previous_results or {})
    results.update(
        {
            "job_post_id": job_post_id,
            "cv_version_id": cv_version_id if cv_version_id is not None else results.get("cv_version_id"),
            "days_remaining": days_remaining,
            "failures": [],
            "resumed_from": resume_from,
            "started_at": utc_now_iso(),
            "use_web_search": use_web_search,
            "proceed_on_poor_fit": proceed_on_poor_fit,
            "top_companies": top_companies,
            "top_titles": top_titles,
            "top_skills": top_skills,
            "fallback_model": fallback_model,
            "primary_model": model,
        }
    )
    # Drop stale retry flags; recomputed at the end.
    results.pop("retry_from", None)
    results.pop("incomplete", None)
    results.pop("notification", None)

    failures: list[dict] = results["failures"]
    log_stage_info(
        f"Pipeline start job #{job_post_id}"
        + (f" resume_from={resume_from}" if resume_from else "")
        + (f" FALLBACK_MODEL={fallback_model}" if fallback_model else "")
    )

    llm = {"fallback_model": fallback_model, "model_pos": 1}
    no_llm = {"model_pos": None}

    # --- Fit ----------------------------------------------------------------
    if _should_run("fit", resume_from, results):
        print("[analysis] Evaluating fit...")
        fit = run_stage(
            "Fit evaluation",
            check_fit,
            client,
            model,
            cv,
            job_post,
            failures=failures,
            job_post_id=job_post_id,
            stage_key="fit",
            **llm,
        )
        results["fit"] = fit
    else:
        fit = results.get("fit")

    if fit is None:
        results["status"] = "error"
        results["statistics"] = run_stage(
            "Statistics",
            refresh_statistics,
            top_companies=top_companies,
            top_titles=top_titles,
            top_skills=top_skills,
            failures=failures,
            job_post_id=job_post_id,
            stage_key="statistics",
            **no_llm,
        )
        results["retry_from"] = "fit"
        results["incomplete"] = True
        results["notification"] = (
            "Fit evaluation failed. Retry from the fit stage to continue. "
            "See logs/analysis.log."
            + (
                f" (FALLBACK_MODEL={fallback_model} was also tried.)"
                if fallback_model
                else " Consider setting FALLBACK_MODEL in .env."
            )
        )
        return results

    verdict = fit.get("verdict")
    reasoning = fit.get("reasoning", "")

    if verdict == "poor_fit" and not proceed_on_poor_fit and resume_from is None:
        print("[analysis] Poor fit — stopping (proceed_on_poor_fit is off).")
        run_stage(
            "Recording analysis",
            update_job_post_analysis,
            job_post_id,
            verdict,
            reasoning,
            "declined",
            cv_version_id,
            failures=failures,
            job_post_id=job_post_id,
            stage_key="record",
            **no_llm,
        )
        results["status"] = "declined"
        results["ranking"] = _store_summary_and_rank(
            client,
            model,
            job_post_id,
            verdict,
            days_remaining,
            None,
            None,
            failures,
            fallback_model=fallback_model,
        )
        results["statistics"] = run_stage(
            "Statistics",
            refresh_statistics,
            top_companies=top_companies,
            top_titles=top_titles,
            top_skills=top_skills,
            failures=failures,
            job_post_id=job_post_id,
            stage_key="statistics",
            **no_llm,
        )
        results["incomplete"] = False
        results["retry_from"] = None
        results["notification"] = (
            "Stopped after poor fit. Turn on 'Proceed even if poor fit' and run again "
            "to generate a learning plan, revised CV, and motivation letter."
        )
        return results

    # Proceeding: aim for plan + CV + letter.
    if resume_from is None or _should_run("gaps", resume_from, results):
        run_stage(
            "Recording analysis",
            update_job_post_analysis,
            job_post_id,
            verdict,
            reasoning,
            "continued",
            cv_version_id,
            failures=failures,
            job_post_id=job_post_id,
            stage_key="record",
            **no_llm,
        )
    results["status"] = "continued"

    date_saved = post.get("date_saved") or get_today()
    stem = output_stem(post.get("company"), post.get("job_title"), date_saved, job_post_id)

    # --- Gaps ---------------------------------------------------------------
    gaps = results.get("gaps")
    rebuilt_gaps = False
    if _should_run("gaps", resume_from, results):
        print(f"[analysis] Gap analysis ({days_remaining} days until deadline)...")
        gaps = run_stage(
            "Gap analysis",
            analyze_gaps,
            client,
            model,
            cv,
            job_post,
            days_remaining,
            failures=failures,
            job_post_id=job_post_id,
            stage_key="gaps",
            **llm,
        )
        if gaps is None:
            log_stage_info("Using fit-check gaps as fallback for learning plan input.")
            gaps = _gaps_fallback_from_fit(fit, days_remaining)
            results["gaps_fallback"] = True
            print(
                "[analysis] Gap analysis failed — using fit-check gaps as a fallback "
                "so the learning plan can still be built."
            )
        else:
            results["gaps_fallback"] = False
            rebuilt_gaps = True
        results["gaps"] = gaps

    # --- Learning plan (always attempted when proceeding) -------------------
    # Rebuild the plan when gaps were just re-run successfully (replace fallback plan).
    if _should_run("plan", resume_from, results) or rebuilt_gaps:
        print("[analysis] Building learning plan...")
        if gaps is None:
            gaps = _gaps_fallback_from_fit(fit, days_remaining)
            results["gaps"] = gaps
            results["gaps_fallback"] = True
        plan = run_stage(
            "Learning plan",
            create_learning_plan,
            client,
            model,
            gaps,
            days_remaining,
            use_web_search,
            failures=failures,
            job_post_id=job_post_id,
            stage_key="plan",
            **llm,
        )
        if plan is not None:
            results["plan"] = plan
            results["plan_path"] = save_learning_plan(plan, stem)
        else:
            results.pop("plan", None)
            results.pop("plan_path", None)

    # --- CV (always attempted when proceeding) ------------------------------
    if _should_run("cv", resume_from, results):
        print("[analysis] Tailoring CV...")
        advice = run_stage(
            "CV tailoring",
            advise_cv,
            client,
            model,
            cv,
            job_post,
            failures=failures,
            job_post_id=job_post_id,
            stage_key="cv",
            **llm,
        )
        if advice is not None:
            results["cv"] = advice
            results["cv_path"] = save_revised_cv(advice["revised_cv"], stem)
        else:
            results.pop("cv", None)
            results.pop("cv_path", None)

    # --- Motivation letter (always attempted when proceeding) ---------------
    if _should_run("letter", resume_from, results):
        print("[analysis] Writing motivation letter...")
        letter = run_stage(
            "Motivation letter",
            create_motivation_letter,
            client,
            model,
            cv,
            job_post,
            failures=failures,
            job_post_id=job_post_id,
            stage_key="letter",
            **llm,
        )
        if letter is not None:
            results["letter"] = letter
            results["letter_path"] = save_motivation_letter(
                letter["motivation_letter"], stem
            )
        else:
            results.pop("letter", None)
            results.pop("letter_path", None)

    # --- Ranking + statistics -----------------------------------------------
    if _should_run("ranking", resume_from, results):
        results["ranking"] = _store_summary_and_rank(
            client,
            model,
            job_post_id,
            verdict,
            days_remaining,
            results.get("gaps"),
            results.get("plan"),
            failures,
            fallback_model=fallback_model,
        )

    if _should_run("statistics", resume_from, results):
        results["statistics"] = run_stage(
            "Statistics",
            refresh_statistics,
            top_companies=top_companies,
            top_titles=top_titles,
            top_skills=top_skills,
            failures=failures,
            job_post_id=job_post_id,
            stage_key="statistics",
            **no_llm,
        )

    _finalize_status(results)
    return results

from openai import OpenAI
from dotenv import load_dotenv
import os
from typing import Callable, TypeVar

from data.cv import load_cv, save_revised_cv
from data.job_post import load_job_post
from data.db import init_db, save_job_post, get_job_post
from data.learning_plan import save_learning_plan
from data.motivation_letter import save_motivation_letter
from agents.match_check import check_fit
from agents.gap_analysis import analyze_gaps
from agents.learning_plan import create_learning_plan
from agents.cv_advisor_agent import advise_cv
from agents.motivation_letter_agent import create_motivation_letter
from utils.date_utils import days_until

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

T = TypeVar("T")


def resolve_web_search() -> bool:
    """Let the user enable/disable web search before the run.

    Defaults to the ENABLE_WEB_SEARCH env var (off by default, since free models have
    no credits for paid search) and lets the user override it interactively.
    """
    default = os.getenv("ENABLE_WEB_SEARCH", "false").strip().lower() in ("1", "true", "yes")
    hint = "Y/n" if default else "y/N"
    answer = input(
        f"Enable web search for study resources? Requires OpenRouter credits [{hint}]: "
    ).strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def run_stage(name: str, func: Callable[..., T], *args, **kwargs) -> T | None:
    """Run a pipeline stage, returning None (instead of crashing) on failure.

    Keeps earlier results/DB writes intact if a later agent fails.
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(f"\n⚠️  {name} failed: {e}\n   Skipping this step and continuing.")
        return None


def main() -> None:
    load_dotenv()
    api_key = os.getenv("API_KEY")
    model = os.getenv("MODEL")
    if not api_key or not model:
        raise ValueError("API_KEY or MODEL not found — check your .env file")

    client = OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL)

    cv = load_cv()
    if cv is None:
        raise FileNotFoundError("No CV found. Paste your CV text into data/cv.txt and run again.")

    job_post = load_job_post()
    if job_post is None:
        raise FileNotFoundError("No job post found. Paste it into data/job_post.txt and run again.")

    init_db()
    use_web_search = resolve_web_search()

    print("\nEvaluating fit...\n")
    result = run_stage("Fit evaluation", check_fit, client, model, cv, job_post)
    if result is None:
        print("Cannot continue without a fit evaluation. Stopping.")
        return

    print(f"Verdict: {result['verdict']}")
    print(f"Reasoning: {result['reasoning']}")
    print(f"Matches: {result['key_matches']}")
    print(f"Gaps: {result['key_gaps']}")

    if result["verdict"] == "poor_fit":
        print("\n⚠️  This looks like a poor fit based on the analysis above.")

    proceed = input("Continue with this job post? (y/n): ").strip().lower()
    status = "continued" if proceed == "y" else "declined"

    print("\nExtracting job post details and saving to database...\n")
    job_post_id = run_stage(
        "Saving job post",
        save_job_post,
        client, model, job_post, result["verdict"], result["reasoning"], status,
    )
    if job_post_id is None:
        print("Could not save the job post. Stopping.")
        return

    if status == "declined":
        print("Stopping here.")
        return

    # CV isn't stored in the DB, so use the in-memory text; reuse the already-extracted
    # deadline from the DB to avoid a second extraction call.
    saved = get_job_post(job_post_id)
    days_remaining = days_until(saved["job_post_deadline"] if saved else None)

    print(f"\nAnalyzing skill gaps ({days_remaining} days until deadline)...\n")
    gaps = run_stage(
        "Gap analysis", analyze_gaps, client, model, cv, job_post, days_remaining
    )
    if gaps is not None:
        print(f"Summary: {gaps['overall_summary']}\n")
        print("Prioritized gaps:")
        for gap in gaps["prioritized_gaps"]:
            fit = "achievable" if gap["achievable_before_deadline"] else "tight"
            print(
                f"  {gap['priority']}. {gap['skill']} [{gap['importance']}] "
                f"~{gap['estimated_days_to_learn']}d ({fit})"
            )
            print(f"     -> {gap['recommendation']}")

        print("\nBuilding a study plan...\n")
        plan = run_stage(
            "Learning plan",
            create_learning_plan,
            client, model, gaps, days_remaining, use_web_search,
        )
        if plan is not None:
            plan_path = save_learning_plan(plan, job_post_id)
            print(
                f"Study plan ({plan['total_estimated_days']}d of "
                f"{plan['days_remaining']}d available): {plan['feasibility_note']}\n"
            )
            for item in plan["items"]:
                print(f"  {item['priority']}. {item['skill']} (~{item['estimated_days']}d)")
                print(f"     What: {item['what']}")
                print(f"     Why:  {item['why']}")
                for res in item["resources"]:
                    print(f"       - {res['name']}: {res['link']}")
            print(f"\nSaved learning plan to {plan_path}")

    print("\nTailoring your CV to this job post...\n")
    advice = run_stage("CV tailoring", advise_cv, client, model, cv, job_post)
    if advice is not None:
        cv_path = save_revised_cv(advice["revised_cv"], job_post_id)
        print("CV recommendations:")
        for rec in advice["recommendations"]:
            print(f"  - [{rec['section']}] {rec['change']}")
            print(f"     Why: {rec['why']}")
        print(f"\nSaved tailored CV to {cv_path}")

    print("\nWriting a motivation letter...\n")
    letter = run_stage(
        "Motivation letter", create_motivation_letter, client, model, cv, job_post
    )
    if letter is not None:
        letter_path = save_motivation_letter(letter["motivation_letter"], job_post_id)
        print(letter["motivation_letter"])
        print(f"\nSaved motivation letter to {letter_path}")


if __name__ == "__main__":
    main()
from config import create_client, web_search_enabled_default
from data.cv import load_cv
from data.job_post import load_job_post
from data.db import init_db
from services.cv_service import ensure_cv_version
from services.job_post_service import add_job_post
from services.analysis_service import run_analysis
from utils.pipeline import run_stage


def resolve_web_search() -> bool:
    """Let the user enable/disable web search before the run.

    Defaults to the ENABLE_WEB_SEARCH env var (off by default, since free models have
    no credits for paid search) and lets the user override it interactively.
    """
    default = web_search_enabled_default()
    hint = "Y/n" if default else "y/N"
    answer = input(
        f"Enable web search for study resources? Requires OpenRouter credits [{hint}]: "
    ).strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def run_cli() -> None:
    client, model = create_client()

    cv = load_cv()
    if cv is None:
        raise FileNotFoundError("No CV found. Paste your CV text into data/cv.txt and run again.")

    job_post = load_job_post()
    if job_post is None:
        raise FileNotFoundError("No job post found. Paste it into data/job_post.txt and run again.")

    init_db()
    use_web_search = resolve_web_search()
    cv_version_id = ensure_cv_version(cv)

    print("\nExtracting job post details and saving to database...\n")
    saved = run_stage("Saving job post", add_job_post, client, model, job_post)
    if saved is None:
        print("Could not save the job post. Stopping.")
        return
    job_post_id = saved["id"]

    results = run_analysis(
        client,
        model,
        job_post_id,
        cv,
        cv_version_id,
        use_web_search=use_web_search,
        proceed_on_poor_fit=True,
    )

    fit = results.get("fit")
    if fit is None:
        print("Fit evaluation failed. Stopping.")
        return

    print(f"\nVerdict: {fit['verdict']}")
    print(f"Reasoning: {fit['reasoning']}")
    print(f"Matches: {fit['key_matches']}")
    print(f"Gaps: {fit['key_gaps']}")
    if fit["verdict"] == "poor_fit":
        print("\n⚠️  This looks like a poor fit based on the analysis above.")

    if results.get("status") == "declined":
        print("\nStopped after fit (poor fit).")
        return

    gaps = results.get("gaps")
    if gaps is not None:
        print(f"\nSummary: {gaps['overall_summary']}\n")
        print("Prioritized gaps:")
        for gap in gaps["prioritized_gaps"]:
            fit_note = "achievable" if gap["achievable_before_deadline"] else "tight"
            print(
                f"  {gap['priority']}. {gap['skill']} [{gap['importance']}] "
                f"~{gap['estimated_days_to_learn']}d ({fit_note})"
            )
            print(f"     -> {gap['recommendation']}")

    plan = results.get("plan")
    if plan is not None:
        print(
            f"\nStudy plan ({plan['total_estimated_days']}d of "
            f"{plan['days_remaining']}d available): {plan['feasibility_note']}"
        )
        for item in plan["items"]:
            print(f"  {item['priority']}. {item['skill']} (~{item['estimated_days']}d)")
        print(f"Saved learning plan to {results.get('plan_path')}")

    if results.get("cv_path"):
        print(f"\nSaved tailored CV to {results['cv_path']}")

    letter = results.get("letter")
    if letter is not None:
        print("\nMotivation letter:\n")
        print(letter["motivation_letter"])
        print(f"\nSaved motivation letter to {results.get('letter_path')}")


if __name__ == "__main__":
    run_cli()

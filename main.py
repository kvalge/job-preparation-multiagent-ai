from openai import OpenAI
from dotenv import load_dotenv
import os

from data.cv import load_cv
from data.job_post import load_job_post
from data.db import init_db, save_job_post, get_job_post
from data.learning_plan import save_learning_plan
from agents.match_check import check_fit
from agents.gap_analysis import analyze_gaps
from agents.learning_plan import create_learning_plan
from utils.date_utils import days_until

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


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

    print("\nEvaluating fit...\n")
    result = check_fit(client, model, cv, job_post)

    print(f"Verdict: {result['verdict']}")
    print(f"Reasoning: {result['reasoning']}")
    print(f"Matches: {result['key_matches']}")
    print(f"Gaps: {result['key_gaps']}")

    if result["verdict"] == "poor_fit":
        print("\n⚠️  This looks like a poor fit based on the analysis above.")

    proceed = input("Continue with this job post? (y/n): ").strip().lower()
    status = "continued" if proceed == "y" else "declined"

    print("\nExtracting job post details and saving to database...\n")
    job_post_id = save_job_post(
        client, model, job_post, result["verdict"], result["reasoning"], status
    )

    if status == "declined":
        print("Stopping here.")
        return

    # CV isn't stored in the DB, so use the in-memory text; reuse the already-extracted
    # deadline from the DB to avoid a second extraction call.
    saved = get_job_post(job_post_id)
    days_remaining = days_until(saved["job_post_deadline"] if saved else None)

    print(f"\nAnalyzing skill gaps ({days_remaining} days until deadline)...\n")
    gaps = analyze_gaps(client, model, cv, job_post, days_remaining)

    print(f"Summary: {gaps['overall_summary']}\n")
    print("Prioritized gaps:")
    for gap in gaps["prioritized_gaps"]:
        fit = "achievable" if gap["achievable_before_deadline"] else "tight"
        print(
            f"  {gap['priority']}. {gap['skill']} [{gap['importance']}] "
            f"~{gap['estimated_days_to_learn']}d ({fit})"
        )
        print(f"     -> {gap['recommendation']}")

    print("\nBuilding a study plan and searching for resources...\n")
    plan = create_learning_plan(client, model, gaps, days_remaining)
    plan_path = save_learning_plan(plan, job_post_id)

    print(
        f"Study plan ({plan['total_estimated_days']}d of {plan['days_remaining']}d "
        f"available): {plan['feasibility_note']}\n"
    )
    for item in plan["items"]:
        print(f"  {item['priority']}. {item['skill']} (~{item['estimated_days']}d)")
        print(f"     What: {item['what']}")
        print(f"     Why:  {item['why']}")
        for res in item["resources"]:
            print(f"       - {res['name']}: {res['link']}")

    print(f"\nSaved learning plan to {plan_path}")


if __name__ == "__main__":
    main()
from openai import OpenAI

from config import create_client, web_search_enabled_default
from data.cv import load_cv
from data.job_post import load_job_post
from data.db import init_db, list_job_posts
from services.cv_service import ensure_cv_version
from services.job_post_service import add_job_post
from services.analysis_service import run_analysis
from utils.pipeline import run_stage


def _post_label(post: dict) -> str:
    name = " — ".join(p for p in (post.get("company"), post.get("job_title")) if p)
    return name or "(untitled)"


def choose_job_post(
    client: OpenAI, model: str, posts: list[dict], pending_text: str | None
) -> int | None:
    """Let the user pick a saved job post, or add a new one from data/job_post.txt.

    Returns the chosen job_posts.id, or None if nothing valid was selected.
    """
    print("\nChoose a job post to analyze:")
    for idx, post in enumerate(posts, start=1):
        print(f"  {idx}. #{post['id']} {_post_label(post)} [{post.get('status')}]")

    new_option = len(posts) + 1
    if pending_text:
        print(f"  {new_option}. Add & analyze a new job post from data/job_post.txt")

    choice = input("Enter number: ").strip()
    if not choice.isdigit():
        print("Invalid choice.")
        return None
    n = int(choice)

    if 1 <= n <= len(posts):
        return posts[n - 1]["id"]
    if pending_text and n == new_option:
        saved = run_stage("Saving job post", add_job_post, client, model, pending_text)
        return saved["id"] if saved else None

    print("Invalid choice.")
    return None


def print_ranking(ranking: dict | None) -> None:
    """Print the cross-post ranking that tells the user which job to pursue first."""
    if not ranking:
        return

    labels = {p["id"]: _post_label(p) for p in list_job_posts()}

    print("\n" + "=" * 60)
    print("WHICH JOB TO PURSUE (ranked by fit + deadline readiness)")
    print("=" * 60)

    for item in ranking.get("ranking", []):
        pid = item.get("job_post_id")
        label = labels.get(pid, f"#{pid}")
        print(
            f"  {item.get('rank')}. #{pid} {label} "
            f"[{item.get('recommendation')}]"
        )
        print(f"     -> {item.get('reason')}")

    top = ranking.get("top_pick") or {}
    if top.get("job_post_id") is not None:
        pid = top["job_post_id"]
        print(f"\nStart here: #{pid} {labels.get(pid, '')}")
        print(f"  {top.get('why', '')}")

    if ranking.get("overall_note"):
        print(f"\n{ranking['overall_note']}")


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

    init_db()

    posts = list_job_posts()
    pending_text = load_job_post()
    if not posts and not pending_text:
        raise FileNotFoundError(
            "No saved job posts and data/job_post.txt is empty. Add a job post via the "
            "web UI, or paste one into data/job_post.txt and run again."
        )

    job_post_id = choose_job_post(client, model, posts, pending_text)
    if job_post_id is None:
        print("Nothing selected. Stopping.")
        return

    use_web_search = resolve_web_search()
    cv_version_id = ensure_cv_version(cv)

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
        print_ranking(results.get("ranking"))
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

    print_ranking(results.get("ranking"))


if __name__ == "__main__":
    run_cli()

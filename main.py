from openai import OpenAI
from dotenv import load_dotenv
import os

from data.cv import load_cv
from data.job_post import load_job_post
from data.db import init_db
from agents.match_check import check_fit

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
    if proceed != "y":
        print("Stopping here.")
        return


if __name__ == "__main__":
    main()
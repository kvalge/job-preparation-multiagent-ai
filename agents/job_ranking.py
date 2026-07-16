import json

from openai import OpenAI
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from openai.types.shared_params import ResponseFormatJSONObject

from utils.date_utils import get_today
from utils.llm_json import parse_json_response

JOB_RANKING_SYSTEM_PROMPT = """You help a candidate decide which job application to pursue first.

You are given several job posts the candidate has already analyzed. For each you know:
- fit verdict (good_fit is best, then stretch_fit, then poor_fit)
- days_remaining until the application deadline (urgency: fewer days = more urgent, but also less time to close gaps)
- gap_count and top_gaps (the main missing skills)
- plan_realistic and plan_total_days: whether the learning plan can realistically be completed, and how many days it needs
- status ("continued" means worth pursuing, "declined" means it was judged a poor fit and set aside)

Rank the jobs to maximise the candidate's chances. Reward jobs that combine a strong fit
with gaps that can realistically be closed before the deadline. Penalise jobs whose plan
needs more days than remain, or whose fit is poor. Treat a soon deadline as urgent only
when the plan can still be finished in time.

Respond ONLY with valid JSON in this exact format, no other text:
{
  "ranking": [
    {
      "job_post_id": 0,
      "rank": 1,
      "recommendation": "pursue" | "maybe" | "skip",
      "reason": "one short sentence explaining this position"
    }
  ],
  "top_pick": {
    "job_post_id": 0,
    "why": "1-2 sentences on why to start here and what the learning path focus should be"
  },
  "overall_note": "1-2 sentence overview to help the candidate decide"
}
Order ranking by rank ascending (1 = best). Include every job you were given exactly once.
"""


def rank_job_posts(client: OpenAI, model: str, jobs: list[dict]) -> dict:
    """Rank analyzed job posts by readiness and deadline, with short reasons.

    Each item in `jobs` should include job_post_id, company, job_title, deadline,
    days_remaining, verdict, status, gap_count, top_gaps, plan_realistic and
    plan_total_days. Returns a dict following the schema in the system prompt.
    """
    system_prompt = (
        f"{JOB_RANKING_SYSTEM_PROMPT}\n\n"
        f"Today's date is {get_today()}. Reason about urgency relative to this date."
    )

    messages: list[ChatCompletionMessageParam] = [
        ChatCompletionSystemMessageParam(role="system", content=system_prompt),
        ChatCompletionUserMessageParam(
            role="user",
            content="Job posts to rank (JSON):\n" + json.dumps(jobs, indent=2),
        ),
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.2,
        response_format=ResponseFormatJSONObject(type="json_object"),
    )
    return parse_json_response(response, context="job ranking")

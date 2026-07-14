from openai import OpenAI
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

from utils.date_utils import get_today
from utils.llm_json import parse_json_response

GAP_ANALYSIS_SYSTEM_PROMPT = """You are a career coach performing a gap analysis between a candidate's CV and a job posting.

For every important requirement or skill in the job post, grade levels on a 0-4 scale:
    0 = none, 1 = beginner, 2 = intermediate, 3 = proficient, 4 = expert
- candidate_level: the level shown in the CV (do NOT reduce to a yes/no — judge depth).
- required_level: the level the role actually needs.
- gap: (required_level - candidate_level), floored at 0.

Then, for each real gap (required_level > candidate_level):
- importance: how essential the skill is to the role — "critical" | "important" | "nice_to_have".
- estimated_days_to_learn: realistic days to reach a usable level for this role.
- achievable_before_deadline: whether that can be done within the days remaining.
- priority: an integer rank (1 = work on first) that BALANCES importance against
  time-to-learn AND the days remaining before the deadline. Prefer gaps that are both
  high-importance and closable in the remaining time. A critical skill that cannot
  realistically be closed in time should still be surfaced, but flagged via
  achievable_before_deadline = false rather than ranked as an easy win.

Respond ONLY with valid JSON in this exact format, no other text:
{
  "skill_assessment": [
    {
      "skill": "name",
      "candidate_level": 0,
      "required_level": 0,
      "gap": 0,
      "importance": "critical" | "important" | "nice_to_have"
    }
  ],
  "prioritized_gaps": [
    {
      "skill": "name",
      "importance": "critical" | "important" | "nice_to_have",
      "estimated_days_to_learn": 0,
      "achievable_before_deadline": true,
      "priority": 1,
      "recommendation": "concrete, specific action to close this gap in the time available"
    }
  ],
  "overall_summary": "2-4 sentences: can the candidate realistically close the key gaps before the deadline, and what to focus on first?"
}
Order prioritized_gaps by priority ascending (1 = highest).
"""


def analyze_gaps(
    client: OpenAI,
    model: str,
    cv: str,
    job_post: str,
    days_remaining: int,
) -> dict:
    """Compare a CV against a job post and produce a deadline-aware gap analysis.

    Grades skill levels (not just yes/no), prioritizes gaps by importance and
    time-to-learn, and weighs them against the days remaining until the deadline.
    Returns a dict following the schema in the system prompt.
    """
    system_prompt = (
        f"{GAP_ANALYSIS_SYSTEM_PROMPT}\n\n"
        f"Today's date is {get_today()}. "
        f"There are {days_remaining} days remaining until the application deadline. "
        f"Weigh every priority decision against this remaining time."
    )

    messages: list[ChatCompletionMessageParam] = [
        ChatCompletionSystemMessageParam(role="system", content=system_prompt),
        ChatCompletionUserMessageParam(
            role="user", content=f"CV:\n{cv}\n\nJob Post:\n{job_post}"
        ),
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    return parse_json_response(response, context="gap analysis")

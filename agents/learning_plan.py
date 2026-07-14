import json

from openai import OpenAI
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

from utils.date_utils import get_today
from utils.llm_json import parse_json_response

LEARNING_PLAN_SYSTEM_PROMPT = """You are a career coach building a realistic, time-boxed study plan that closes the skill
gaps identified for a specific job application, before its deadline.

You will receive a gap analysis (prioritized skill gaps). Turn it into a concrete plan:
- Cover gaps in priority order. Focus on what most improves the candidate's chances.
- For each item, USE WEB SEARCH to find real, currently-available study resources
  (courses, docs, tutorials, videos). Every resource MUST have a real, working URL —
  never invent links. Prefer reputable, free-or-affordable, up-to-date sources.
- Be REALISTIC about time. The sum of estimated_days across all items MUST NOT exceed
  the days remaining until the deadline. If everything cannot fit, include only what
  realistically fits by priority and explain what was deferred in feasibility_note.

Respond ONLY with valid JSON in this exact format, no other text:
{
  "days_remaining": 0,
  "total_estimated_days": 0,
  "realistic": true,
  "feasibility_note": "1-3 sentences on whether the plan fits the deadline and what was deferred, if anything",
  "items": [
    {
      "priority": 1,
      "skill": "skill name",
      "what": "short description of what exactly to study",
      "why": "short description of why it matters for this role / which gap it closes",
      "estimated_days": 1,
      "resources": [
        {
          "name": "resource title",
          "description": "what it is and why it's useful",
          "link": "https://real-url"
        }
      ]
    }
  ]
}
Order items by priority ascending (1 = do first).
"""


def create_learning_plan(
    client: OpenAI,
    model: str,
    gap_analysis: dict,
    days_remaining: int,
) -> dict:
    """Build a realistic, deadline-aware study plan from a gap analysis result.

    Uses web search to attach real study resources (name, description, link) to each
    item, estimates study time per item, and keeps the total within days_remaining.
    Returns a dict following the schema in the system prompt.
    """
    system_prompt = (
        f"{LEARNING_PLAN_SYSTEM_PROMPT}\n\n"
        f"Today's date is {get_today()}. "
        f"There are {days_remaining} days remaining until the application deadline. "
        f"The plan must be completable within that time."
    )

    messages: list[ChatCompletionMessageParam] = [
        ChatCompletionSystemMessageParam(role="system", content=system_prompt),
        ChatCompletionUserMessageParam(
            role="user",
            content=f"Gap analysis:\n{json.dumps(gap_analysis, indent=2)}",
        ),
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.3,
        extra_body={
            "tools": [
                {"type": "openrouter:web_search", "parameters": {"max_results": 5}}
            ]
        },
    )
    return parse_json_response(response, context="learning plan")

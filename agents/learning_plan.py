import json

from openai import OpenAI, APIError
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
{resource_instruction}
- Be REALISTIC about time. The sum of estimated_days across all items MUST NOT exceed
  the days remaining until the deadline. If everything cannot fit, include only what
  realistically fits by priority and explain what was deferred in feasibility_note.

Respond ONLY with valid JSON in this exact format, no other text:
{{
  "days_remaining": 0,
  "total_estimated_days": 0,
  "realistic": true,
  "feasibility_note": "1-3 sentences on whether the plan fits the deadline and what was deferred, if anything",
  "items": [
    {{
      "priority": 1,
      "skill": "skill name",
      "what": "short description of what exactly to study",
      "why": "short description of why it matters for this role / which gap it closes",
      "estimated_days": 1,
      "resources": [
        {{
          "name": "resource title",
          "description": "what it is and why it's useful",
          "link": "https://real-url"
        }}
      ]
    }}
  ]
}}
Order items by priority ascending (1 = do first).
"""

_RESOURCE_INSTRUCTION_WEB = """- For each item, USE THE WEB SEARCH RESULTS provided to find real, currently-available
  study resources (courses, docs, tutorials, videos). Every resource MUST have a real,
  working URL — never invent links. Prefer reputable, free-or-affordable, up-to-date sources."""

_RESOURCE_INSTRUCTION_NO_WEB = """- For each item, recommend well-known, reputable study resources (courses, docs,
  tutorials, videos) that you are confident exist, using the official site's URL. Do NOT
  fabricate specific URLs you are unsure about — prefer a resource's known official page.
  Note in feasibility_note that resource links were not verified against live search."""


def _build_messages(
    gap_analysis: dict, days_remaining: int, web_enabled: bool
) -> list[ChatCompletionMessageParam]:
    resource_instruction = (
        _RESOURCE_INSTRUCTION_WEB if web_enabled else _RESOURCE_INSTRUCTION_NO_WEB
    )
    system_prompt = (
        f"{LEARNING_PLAN_SYSTEM_PROMPT.format(resource_instruction=resource_instruction)}\n\n"
        f"Today's date is {get_today()}. "
        f"There are {days_remaining} days remaining until the application deadline. "
        f"The plan must be completable within that time."
    )
    return [
        ChatCompletionSystemMessageParam(role="system", content=system_prompt),
        ChatCompletionUserMessageParam(
            role="user",
            content=f"Gap analysis:\n{json.dumps(gap_analysis, indent=2)}",
        ),
    ]


def create_learning_plan(
    client: OpenAI,
    model: str,
    gap_analysis: dict,
    days_remaining: int,
    use_web_search: bool = False,
) -> dict:
    """Build a realistic, deadline-aware study plan from a gap analysis result.

    When use_web_search is True, enriches resources with OpenRouter's web search plugin
    (falling back to the model's own knowledge if search fails, e.g. no credits). When
    False, skips search entirely and uses the model's knowledge. Returns a dict following
    the schema above.
    """
    if use_web_search:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=_build_messages(gap_analysis, days_remaining, web_enabled=True),
                temperature=0.3,
                extra_body={"plugins": [{"id": "web", "max_results": 5}]},
            )
            return parse_json_response(response, context="learning plan")
        except APIError as e:
            message = getattr(e, "message", str(e))
            print(
                f"  (Web search unavailable: {message}. "
                "Building plan from model knowledge.)"
            )

    response = client.chat.completions.create(
        model=model,
        messages=_build_messages(gap_analysis, days_remaining, web_enabled=False),
        temperature=0.3,
    )
    return parse_json_response(response, context="learning plan")

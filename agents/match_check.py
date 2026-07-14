from openai import OpenAI
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

from utils.date_utils import get_today
from utils.llm_json import parse_json_response

MATCH_CHECK_SYSTEM_PROMPT = """You evaluate how well a candidate's CV fits a specific job posting.

When assessing experience, education, certifications, or training with date ranges, compare the end date to today's date to determine 
whether it is completed, in progress, or upcoming. Do not assume something is incomplete just because it has an end date in the CV — 
check whether that end date has already passed.

Respond ONLY with valid JSON in this exact format, no other text:
{
  "verdict": "good_fit" | "stretch_fit" | "poor_fit",
  "reasoning": "2-3 sentence explanation",
  "key_matches": ["list of things that align well"],
  "key_gaps": ["list of major missing requirements"]
}
"""


def check_fit(client: OpenAI, model: str, cv: str, job_post: str) -> dict:
    """Evaluate whether the CV is a good fit for the job post. Returns a dict."""
    system_prompt = (
        f"{MATCH_CHECK_SYSTEM_PROMPT}\n\n"
        f"Today's date is {get_today()}. Use this to judge whether dated experience, "
        f"education, or training is completed, ongoing, or upcoming."
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
    return parse_json_response(response, context="match check")
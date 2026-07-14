from openai import OpenAI
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from openai.types.shared_params import ResponseFormatJSONObject

from utils.date_utils import get_today
from utils.llm_json import parse_json_response

CV_ADVISOR_SYSTEM_PROMPT = """You are an expert CV/resume editor tailoring a candidate's CV to a specific job posting.

Your job has two parts:
1. Recommend concrete, specific changes that make the CV align better with the job's
   requirements — reordering, rephrasing, quantifying achievements, surfacing relevant
   experience, mirroring the posting's terminology, trimming irrelevant content, and
   fixing weak wording.
2. Produce a revised CV that implements those recommendations.

ABSOLUTE RULE — NEVER FABRICATE. You may only use information already present in the
candidate's CV. Do NOT invent employers, titles, dates, degrees, certifications,
metrics, or skills the candidate did not claim. You may rephrase, reorganize, emphasize,
and align wording with the job post, but every factual claim in the revised CV must be
supported by the original CV. If the CV lacks something the job wants, do NOT add it —
instead note the genuine gap in the recommendations.

DATES: Use today's date to phrase dated items correctly. If an end date has already
passed, present it as completed — do NOT keep wording like "(expected completion)" or
"(in progress)" for something whose end date is in the past. If the end date is still in
the future, it is ongoing/upcoming. Never change the actual dates themselves.

Respond ONLY with valid JSON in this exact format, no other text:
{
  "recommendations": [
    {
      "section": "which part of the CV this applies to (e.g. 'Summary', 'Experience - Acme Corp', 'Skills')",
      "change": "what to change",
      "why": "why this helps align with the job post"
    }
  ],
  "revised_cv": "the full revised CV as clean, ready-to-use plain text / markdown"
}
"""


def advise_cv(client: OpenAI, model: str, cv: str, job_post: str) -> dict:
    """Analyze a CV against a job post, recommend truthful changes, and rewrite the CV.

    Returns a dict with 'recommendations' (list of section/change/why) and 'revised_cv'
    (the rewritten CV text). Never fabricates information not present in the original CV.
    """
    system_prompt = (
        f"{CV_ADVISOR_SYSTEM_PROMPT}\n\n"
        f"Today's date is {get_today()}. Use it to judge whether dated experience, "
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
        temperature=0.3,
        response_format=ResponseFormatJSONObject(type="json_object"),
    )
    return parse_json_response(response, context="cv advisor")

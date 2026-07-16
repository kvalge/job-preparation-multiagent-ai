from openai import OpenAI
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from openai.types.shared_params import ResponseFormatJSONObject

from utils.date_utils import get_today
from utils.llm_json import parse_json_response

JOB_POST_EXTRACTION_SYSTEM_PROMPT = """You extract structured information from a job posting.

Extract only what is explicitly stated or can be confidently inferred from the text.
If a field is not present or cannot be determined, use null (do not guess).
If the deadline is written relative to today (e.g. "apply within 2 weeks"), resolve it
to an absolute ISO date using today's date.

Respond ONLY with valid JSON in this exact format, no other text:
{
  "company": "company name" | null,
  "job_title": "role title" | null,
  "salary": "salary as written, e.g. '50-70k EUR/year'" | null,
  "location_type": "remote" | "onsite" | "hybrid" | null,
  "job_post_deadline": "ISO date string, e.g. '2026-08-01'" | null,
  "disclaimers": ["list of legal/equal-opportunity/other disclaimer sentences"],
  "summary": "2-3 sentence summary of the role" | null,
  "skills": ["list of individual required or preferred skills"]
}
"""


def extract_job_post(client: OpenAI, model: str, job_post: str) -> dict:
    """Extract structured fields from a job post. Returns a dict matching the schema above."""
    system_prompt = (
        f"{JOB_POST_EXTRACTION_SYSTEM_PROMPT}\n\n"
        f"Today's date is {get_today()}. Use it to resolve any relative deadlines."
    )

    messages: list[ChatCompletionMessageParam] = [
        ChatCompletionSystemMessageParam(role="system", content=system_prompt),
        ChatCompletionUserMessageParam(role="user", content=f"Job Post:\n{job_post}"),
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.2,
        response_format=ResponseFormatJSONObject(type="json_object"),
    )
    return parse_json_response(response, context="job post extraction")

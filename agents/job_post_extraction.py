import json

from openai import OpenAI
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

JOB_POST_EXTRACTION_SYSTEM_PROMPT = """You extract structured information from a job posting.

Extract only what is explicitly stated or can be confidently inferred from the text.
If a field is not present or cannot be determined, use null (do not guess).

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
    messages: list[ChatCompletionMessageParam] = [
        ChatCompletionSystemMessageParam(
            role="system", content=JOB_POST_EXTRACTION_SYSTEM_PROMPT
        ),
        ChatCompletionUserMessageParam(role="user", content=f"Job Post:\n{job_post}"),
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.2,
    )
    raw = response.choices[0].message.content or "{}"
    return json.loads(raw)

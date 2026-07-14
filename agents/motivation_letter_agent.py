from openai import OpenAI
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from openai.types.shared_params import ResponseFormatJSONObject

from utils.date_utils import get_today
from utils.llm_json import parse_json_response

MOTIVATION_LETTER_SYSTEM_PROMPT = """You write a motivation letter for a candidate applying to a specific job.

TONE & STYLE:
- Serious, simple, and modest. Clear, plain wording.
- No exaggerated or grandiose phrases (avoid "passionate", "world-class",
  "perfect fit", "dream job", "I would be thrilled", hyperbole, or clichés).
- Confident but understated. Short, direct sentences.

LENGTH: Keep it well under one A4 page (roughly 250-350 words, 3-4 short paragraphs).

CONTENT:
- State clearly why the candidate is applying to THIS company and THIS position
  (reference concrete aspects of the role/company from the job post).
- Briefly connect the candidate's genuine, CV-supported experience to the role's needs.
- Close with a simple, non-pushy note of interest.

ABSOLUTE RULE — NEVER FABRICATE. Only use facts present in the candidate's CV. Do not
invent experience, skills, employers, or achievements. If the CV lacks something, do not
claim it.

Respond ONLY with valid JSON in this exact format, no other text:
{
  "motivation_letter": "the full letter as clean, ready-to-use plain text / markdown"
}
"""


def create_motivation_letter(
    client: OpenAI, model: str, cv: str, job_post: str
) -> dict:
    """Write a concise, modest motivation letter tailored to the job post.

    Returns a dict with 'motivation_letter'. Never fabricates information not in the CV.
    """
    system_prompt = (
        f"{MOTIVATION_LETTER_SYSTEM_PROMPT}\n\n"
        f"Today's date is {get_today()}."
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
    return parse_json_response(response, context="motivation letter")

import json
from typing import Any


def parse_json_response(response: Any, context: str = "model response") -> dict:
    """Parse a chat completion into a dict, tolerating fences and surrounding prose.

    Raises a clear ValueError (instead of a cryptic TypeError/KeyError) when the model
    returns empty content, a malformed response object, or something that isn't valid JSON.
    """
    choices = getattr(response, "choices", None)
    if not choices:
        raise ValueError(
            f"Empty or missing choices from {context}. "
            "The API returned no completion choices — often a free-model rate limit, "
            "provider glitch, or unsupported response_format. Retry the stage."
        )

    choice = choices[0]
    message = getattr(choice, "message", None)
    if message is None:
        raise ValueError(
            f"Missing message on first choice from {context} "
            f"(finish_reason={getattr(choice, 'finish_reason', None)})."
        )

    content = getattr(message, "content", None)

    # Some models return content as a list of parts instead of a plain string.
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and part.get("text"):
                parts.append(str(part["text"]))
            else:
                text_attr = getattr(part, "text", None)
                if text_attr:
                    parts.append(str(text_attr))
        content = "".join(parts)

    if not content or not str(content).strip():
        finish_reason = getattr(choice, "finish_reason", None)
        raise ValueError(
            f"Empty content from {context} (finish_reason={finish_reason}). "
            "The model returned no text — check the model supports the request "
            "(e.g. JSON output) and that you have credits / are not rate-limited."
        )

    text = str(content).strip()

    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        raise ValueError(
            f"Could not parse JSON from {context}. Raw content:\n{content}"
        )

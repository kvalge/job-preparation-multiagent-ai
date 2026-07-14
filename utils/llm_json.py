import json
from typing import Any


def parse_json_response(response: Any, context: str = "model response") -> dict:
    """Parse a chat completion into a dict, tolerating fences and surrounding prose.

    Raises a clear ValueError (instead of a downstream KeyError) when the model
    returns empty content or something that isn't valid JSON.
    """
    choice = response.choices[0]
    content = choice.message.content

    if not content or not content.strip():
        finish_reason = getattr(choice, "finish_reason", None)
        raise ValueError(
            f"Empty content from {context} (finish_reason={finish_reason}). "
            "The model returned no text — check the model supports the request "
            "(e.g. tool calling / JSON output) and that you have credits."
        )

    text = content.strip()

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

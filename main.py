from openai import OpenAI
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
    ChatCompletionAssistantMessageParam,
)
from dotenv import load_dotenv
import os

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
SYSTEM_PROMPT = "You are a helpful educational tutor."
EXIT_COMMANDS = {"exit", "quit"}


def main() -> None:
    load_dotenv()
    api_key = os.getenv("API_KEY")
    model = os.getenv("MODEL")

    if not api_key or not model:
        raise ValueError("API_KEY or MODEL not found — check your .env file")

    client = OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL)

    messages: list[ChatCompletionMessageParam] = [
        ChatCompletionSystemMessageParam(role="system", content=SYSTEM_PROMPT)
    ]

    while True:
        question = input("You: ")
        if question.lower() in EXIT_COMMANDS:
            break

        messages.append(
            ChatCompletionUserMessageParam(role="user", content=question)
        )
        print("Thinking...\n")

        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
            )
        except Exception as error:
            print(f"\nError: {error}\n")
            messages.pop()  # drop the question we couldn't answer
            continue

        answer = response.choices[0].message.content or ""
        messages.append(
            ChatCompletionAssistantMessageParam(role="assistant", content=answer)
        )

        print("\nAI:", answer)
        print("\n-------------------\n")


if __name__ == "__main__":
    main()

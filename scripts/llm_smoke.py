from __future__ import annotations

import argparse
import json

from alfred.core.llm_config import LLMProvider
from alfred.services.llm_service import LLMService
from pydantic import BaseModel


class DemoSchema(BaseModel):
    topic: str
    bullets: list[str]


def main() -> None:
    parser = argparse.ArgumentParser(description="Quick LLM smoke check")
    parser.add_argument("prompt", nargs="?", default="Say hello in one short sentence.")
    parser.add_argument("--provider", default=None, choices=[p.value for p in LLMProvider])
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    svc = LLMService()
    msgs = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": args.prompt},
    ]

    provider = LLMProvider(args.provider) if args.provider else None
    text = svc.chat(msgs, provider=provider, model=args.model)
    print("--- chat ---")
    print(text)

    # Structured (OpenAI only)
    msgs_struct = [
        {"role": "system", "content": "Return valid JSON only."},
        {
            "role": "user",
            "content": "Create 3 bullets about LangGraph. Use a neutral tone.",
        },
    ]
    try:
        print("--- structured (OpenAI) ---")
        data = svc.structured(msgs_struct, schema=DemoSchema)
        print(json.dumps(data.model_dump(), indent=2))
    except Exception as e:  # noqa: BLE001
        print(f"Structured output skipped or failed: {e}")


if __name__ == "__main__":
    main()

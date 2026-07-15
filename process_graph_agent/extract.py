from __future__ import annotations

import json
import sys

from llm_client import get_client
from schemas import ExtractionResult

MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """You are analyzing a raw, messy interview transcript in which an \
operator describes their day-to-day work process. The transcript is auto-transcribed \
and imperfect: people backtrack, contradict themselves, go on tangents, and describe \
steps out of order.

Your job is ONLY to identify distinct process activities (steps) mentioned in the \
transcript. Do not order them yet -- that happens in a later stage.

Rules:
- Each activity must be grounded in a VERBATIM quote copied exactly from the transcript. \
Do not paraphrase into the quote field -- copy the exact substring.
- If you believe something is a step but cannot find a clean supporting quote, still \
include it but set grounded=false and explain why in `note`.
- Skip small talk, introductions, and tangents unrelated to the actual work process.
- Use `type="gateway"` for decision/branch points (e.g. "is the customer a prepayment \
customer?"), `type="sendTask"` for steps that hand off to another person/system and wait \
for a reply, `type="subProcess"` for repeated/looped groups of steps (e.g. "for each \
order line"), and `type="task"` for everything else.
- Merge duplicate mentions of the same real-world step into a single activity -- don't \
emit the same step twice just because it was mentioned twice.
- Give each activity a short, clear `label` and a unique `ref` like "A1", "A2", ...
"""

USER_PROMPT_TEMPLATE = """Transcript:
---
{transcript}
---

Extract the process activities as instructed."""


def extract_activities(transcript: str, *, model: str = MODEL) -> ExtractionResult:
    client = get_client()

    tool_schema = ExtractionResult.model_json_schema()

    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        tools=[
            {
                "name": "record_activities",
                "description": "Record the extracted process activities.",
                "input_schema": tool_schema,
            }
        ],
        tool_choice={"type": "tool", "name": "record_activities"},
        messages=[{"role": "user", "content": USER_PROMPT_TEMPLATE.format(transcript=transcript)}],
    )

    tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
    if not tool_use_blocks:
        raise RuntimeError(f"Model did not return a tool_use block. Response: {response}")

    return ExtractionResult.model_validate(tool_use_blocks[0].input)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    if len(sys.argv) != 2:
        print("Usage: python extract.py <transcript_path>", file=sys.stderr)
        sys.exit(1)

    text = open(sys.argv[1], encoding="utf-8").read()
    result = extract_activities(text)
    print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))

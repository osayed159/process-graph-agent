from __future__ import annotations

import json
import sys

from llm_client import get_client
from schemas import Activity, OrderingResult

MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """You are given a list of process activities already extracted from an \
interview transcript, plus the transcript itself. Your job is to work out how these \
activities connect: sequence and conditional branches.

Rules:
- CRITICAL: every single activity `ref` you were given must appear in at least one edge,
either as a source or a target. Before you finish, re-check your activity list against your
edge list and make sure none were left out. If the transcript describes a step that happens
in parallel with, or as a sub-thread of, the main flow (e.g. a production/assembly process
triggered by the main order flow), still connect it: add an edge from whichever activity
triggers it, and if the transcript doesn't say exactly where it rejoins the main flow, connect
its last step onward with `inferred=true` rather than leaving it disconnected. An activity with
zero edges is treated as a pipeline bug, not an acceptable output.
- Every edge connects two activities by their `ref` (source_ref -> target_ref).
- If an edge represents a conditional branch (e.g. "if in stock -> ... otherwise -> ..."), \
set `condition` to a short description of the condition, and set `is_default_branch=true` \
on whichever branch is the fallback/else case.
- Every edge should carry a verbatim supporting `quote` from the transcript wherever the \
order/condition is actually stated. If the order is only implied by the narrative sequence \
of the interview (not explicitly stated), leave `quote` as null and set `inferred=true`.
- The transcript is messy: people backtrack, restate things, and correct themselves. When \
a later statement clearly corrects or supersedes an earlier one, follow the corrected \
version and prefer it for the edge's quote.
- If activities contradict each other about ordering and you cannot tell which is correct, \
still produce your best-guess edge but set `inferred=true` so it is flagged downstream.
- Identify exactly one `start_ref` (the first step of the process) and at least one \
`terminal_ref` (step(s) where the process ends).
- Do not invent activities or edges to/from refs that are not in the provided list.
"""

USER_PROMPT_TEMPLATE = """Transcript:
---
{transcript}
---

Activities (already extracted, do not add/remove/rename any):
---
{activities_json}
---

Work out the ordering and branching as instructed."""


def order_activities(transcript: str, activities: list[Activity], *, model: str = MODEL) -> OrderingResult:
    client = get_client()

    tool_schema = OrderingResult.model_json_schema()
    activities_json = json.dumps([a.model_dump() for a in activities], indent=2, ensure_ascii=False)

    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        tools=[
            {
                "name": "record_ordering",
                "description": "Record the ordering and branching between activities.",
                "input_schema": tool_schema,
            }
        ],
        tool_choice={"type": "tool", "name": "record_ordering"},
        messages=[
            {
                "role": "user",
                "content": USER_PROMPT_TEMPLATE.format(transcript=transcript, activities_json=activities_json),
            }
        ],
    )

    tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
    if not tool_use_blocks:
        raise RuntimeError(f"Model did not return a tool_use block. Response: {response}")

    result = OrderingResult.model_validate(tool_use_blocks[0].input)

    known_refs = {a.ref for a in activities}
    bad_refs = set()
    for e in result.edges:
        if e.source_ref not in known_refs:
            bad_refs.add(e.source_ref)
        if e.target_ref not in known_refs:
            bad_refs.add(e.target_ref)
    if result.start_ref not in known_refs:
        bad_refs.add(result.start_ref)
    bad_refs.update(r for r in result.terminal_refs if r not in known_refs)

    if bad_refs:
        raise ValueError(f"Model referenced unknown activity refs: {sorted(bad_refs)}")

    return result


if __name__ == "__main__":
    from dotenv import load_dotenv

    from extract import extract_activities

    load_dotenv()

    if len(sys.argv) != 2:
        print("Usage: python order.py <transcript_path>", file=sys.stderr)
        sys.exit(1)

    text = open(sys.argv[1], encoding="utf-8").read()
    extraction = extract_activities(text)
    result = order_activities(text, extraction.activities)
    print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))

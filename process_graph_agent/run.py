from __future__ import annotations

import argparse
import json
import sys

from dotenv import load_dotenv

import extract as extract_module
import order as order_module
from assemble import assemble
from check import run_checks


def build_graph(transcript_path: str, *, extract_model: str | None = None, order_model: str | None = None) -> dict:
    transcript = open(transcript_path, encoding="utf-8").read()

    extract_model = extract_model or extract_module.MODEL
    order_model = order_model or order_module.MODEL

    print(f"[1/4] extracting activities from {transcript_path} (model={extract_model}) ...", file=sys.stderr)
    extraction = extract_module.extract_activities(transcript, model=extract_model)
    print(f"      -> {len(extraction.activities)} candidate activities", file=sys.stderr)

    print(f"[2/4] working out ordering & branches (model={order_model}) ...", file=sys.stderr)
    ordering = order_module.order_activities(transcript, extraction.activities, model=order_model)
    print(f"      -> {len(ordering.edges)} candidate edges", file=sys.stderr)

    print("[3/4] assembling graph (dedup, stable IDs, canonical order) ...", file=sys.stderr)
    graph = assemble(extraction, ordering)
    print(f"      -> {len(graph['nodes'])} nodes, {len(graph['edges'])} edges after assembly", file=sys.stderr)

    print("[4/4] running structural + grounding checks ...", file=sys.stderr)
    graph = run_checks(graph, transcript)
    validation = graph["validation"]
    status = "PASSED" if validation["passed"] else "FAILED"
    print(
        f"      -> {status} "
        f"({len(validation['structural_problems'])} structural, "
        f"{len(validation['grounding_problems'])} grounding problems)",
        file=sys.stderr,
    )

    graph["source_transcript"] = transcript_path
    return graph


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Build a process graph from an interview transcript.")
    parser.add_argument("transcript", help="Path to the transcript .txt file")
    parser.add_argument("--out", help="Path to write the output graph JSON (default: stdout)")
    parser.add_argument("--extract-model", help="Override the model used for Stage 1 (extraction)")
    parser.add_argument("--order-model", help="Override the model used for Stage 2 (ordering)")
    parser.add_argument("--model", help="Override the model used for both stages")
    args = parser.parse_args()

    extract_model = args.extract_model or args.model
    order_model = args.order_model or args.model

    graph = build_graph(args.transcript, extract_model=extract_model, order_model=order_model)
    output = json.dumps(graph, indent=2, ensure_ascii=False)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Wrote graph to {args.out}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()

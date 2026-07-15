# Approach — Transcript-to-Process-Graph Agentic System

## Goal

Take a messy interview transcript and produce a structured **process graph**
(activities as nodes, ordering/branches as edges), grounded in what was
actually said. Calibrate against `Graph/graph_1.json` (hand-built from
`transcript_1.txt`), then run on `transcript_2.txt` with no reference to
lean on as a generalization test.

## Why not one-shot

A single "transcript in, JSON out" call can't be checked or debugged — if it
hallucinates a step, there's no way to tell short of manually re-reading the
transcript. Splitting into stages makes each step small enough to verify
independently.

## Pipeline

Plain Python calling Claude directly. The transcripts
fit in a single context window (~15–20k tokens), so no chunking.

1. **Extract activities** (LLM) — identify candidate process steps, each with
   a verbatim supporting quote. This is what makes grounding checkable
   later, not just asserted.
2. **Order & branch** (LLM) — sequence and conditionals ("if in stock → ...,
   otherwise → ..."), each edge quote-grounded or explicitly marked
   `inferred` if the transcript only implies the order.
3. **Assemble** (deterministic, no LLM) — stable content-derived node IDs,
   de-duplication of near-identical activities (fuzzy label match), and
   canonical ordering (BFS from start — the graph isn't a DAG; obstacle
   steps loop back). This is what makes re-running the pipeline idempotent
   rather than trusting the LLM to be consistent.
4. **Check** (mandatory, deterministic) — **structural validation**
   (`networkx`: no dangling edges, every node reachable, clear start/
   terminal) and **grounding** (does each quote actually appear in the
   transcript — exact or fuzzy match). Anything that fails is flagged in
   the output, never silently dropped or invented.

## Failure handling

- Ungrounded nodes/edges are marked `grounded: false` rather than resolved
  by guessing; contradictory statements become a flagged ambiguity, not a
  silent pick.
- Malformed LLM output is prevented, not caught after the fact — Pydantic
  schemas via forced tool-calls mean the model literally cannot return
  something that doesn't parse.
- Non-determinism is addressed by design (stable IDs, dedup, canonical
  order in assembly) rather than chasing bit-for-bit reproducibility, which
  isn't realistic with an LLM in the loop.

## Results

**transcript_1** (Haiku, both stages): 52 nodes/53 edges, 0 grounding
failures, 1 structural failure — one node left unreachable because the
extraction pass surfaced the same real step twice under different wording
("contact production planning..." vs. "request production...", 76% string
similarity, below the 88% dedup threshold), and ordering only wired one
copy in. The checking stage caught it correctly rather than shipping an
invisible orphan. Separately, 52 nodes vs. `graph_1.json`'s 72 — Haiku
extracts coarser-grained steps than the hand-built reference, missing most
of the small "Hindernis" sub steps.

**transcript_2**: first run (Haiku both
stages) left an entire 15-node cluster disconnected not just one dangling
node, a whole thread (production/assembly/MES steps) with zero edges even
among themselves. Strengthening the ordering prompt didn't fix it (18
disconnected on retry). Haiku capability ceiling on sequencing ~60
activities while keeping every thread connected, not a prompt gap.
Escalating just Stage 2 (ordering) to Sonnet — extraction stayed on
Haiku, fixed it completely (0 structural problems); `run.py` now takes
`--extract-model`/`--order-model` independently, since this run is
concrete evidence the two stages have different capability needs. 5
grounding flags remain in the final output; I inspected all of them —
every one is genuine light paraphrase (e.g. real text "vielleicht überfahr
ich irgendeinen anderen Auftrag" vs. quoted "Überfahre ich einen anderen
Auftrag"), on both Haiku and Sonnet output, so "quote verbatim" is a soft
instruction for current models regardless of size.

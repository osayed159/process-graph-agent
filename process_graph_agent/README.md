# Transcript → Process Graph

Takes a messy interview transcript and produces a structured process graph: activities as nodes,
ordering/branches as edges, every node and edge grounded in a quote from
the transcript.

## Setup

```bash
cd process_graph_agent
python -m venv .venv

# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file in this folder with
your Anthropic key

## Run

```bash
python run.py ../Anonymized_Transcripts/transcript_1.txt --out transcript_1_graph.json
python run.py ../Anonymized_Transcripts/transcript_2.txt --out transcript_2_graph.json
```

Progress and a pass/fail validation summary print to stderr as it runs;
the graph JSON goes to the `--out` file (or stdout if `--out` is omitted).

By default, Stage 1 (extraction) and Stage 2 (ordering) both use Claude
Haiku, for cost. You can override either or both independently:

```bash
# use a stronger model just for the harder ordering/branching step
python run.py ../Anonymized_Transcripts/transcript_2.txt --order-model claude-sonnet-5 --out transcript_2_graph.json

# override both stages at once
python run.py ../Anonymized_Transcripts/transcript_1.txt --model claude-sonnet-5 --out transcript_1_graph.json
```

## Output shape

```jsonc
{
  "nodes": [
    { "id": "n_receive_order", "label": "...", "type": "task", "quote": "...",
      "grounded": true, "grounding_verified": true, "note": null }
  ],
  "edges": [
    { "source": "n_receive_order", "target": "n_check_stock",
      "condition": null, "default": false, "quote": "...",
      "grounded": true, "grounding_verified": true, "inferred": false }
  ],
  "start": "n_receive_order",
  "terminals": ["n_send_invoice"],
  "dropped_edges": [ /* edges the assemble stage couldn't resolve, with why */ ],
  "validation": {
    "passed": false,
    "structural_problems": [ /* e.g. unreachable_node, dangling_edge */ ],
    "grounding_problems": [ /* e.g. ungrounded_node, ungrounded_edge */ ]
  },
  "source_transcript": "../Anonymized_Transcripts/transcript_2.txt"
}
```

`validation.passed = false` is expected and meaningful, not a bug to hide

## Pipeline stages (source files)

| File | Stage | Calls the LLM? |
|---|---|---|
| `schemas.py` | shared contracts (Pydantic) | — |
| `extract.py` | 1: identify activities, each with a supporting quote | yes |
| `order.py` | 2: work out sequence & branches between activities | yes |
| `assemble.py` | 3: stable IDs, de-dup, canonical ordering | no (pure code) |
| `check.py` | 4: structural validation + grounding verification | no (pure code) |
| `run.py` | CLI driver wiring all four stages together | — |


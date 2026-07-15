from __future__ import annotations

import hashlib
import re
from collections import deque

from rapidfuzz import fuzz

from schemas import Activity, ExtractionResult, OrderingResult

DEDUPE_SIMILARITY_THRESHOLD = 88


def slugify(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return f"n_{slug}" if slug else "n_step"


def _dedupe(activities: list[Activity]) -> tuple[dict[str, Activity], dict[str, str]]:
    """Merge near-identical activities. Returns (id -> Activity, orig_ref -> id)."""
    kept: dict[str, Activity] = {}
    ref_to_id: dict[str, str] = {}
    used_slugs: dict[str, int] = {}

    for activity in activities:
        match_id = None
        for existing_id, existing in kept.items():
            if fuzz.token_sort_ratio(activity.label, existing.label) >= DEDUPE_SIMILARITY_THRESHOLD:
                match_id = existing_id
                break

        if match_id is not None:
            ref_to_id[activity.ref] = match_id
            continue

        base_slug = slugify(activity.label)
        if base_slug in used_slugs:
            used_slugs[base_slug] += 1
            content_hash = hashlib.sha1(activity.quote.encode("utf-8")).hexdigest()[:4]
            node_id = f"{base_slug}_{content_hash}"
        else:
            used_slugs[base_slug] = 1
            node_id = base_slug

        kept[node_id] = activity
        ref_to_id[activity.ref] = node_id

    return kept, ref_to_id


def _canonical_order(start_id: str, node_ids: set[str], edges: list[dict]) -> list[str]:
    adjacency: dict[str, list[str]] = {nid: [] for nid in node_ids}
    for e in edges:
        if e["source"] in adjacency:
            adjacency[e["source"]].append(e["target"])

    ordered: list[str] = []
    visited: set[str] = set()
    queue: deque[str] = deque()
    if start_id in node_ids:
        queue.append(start_id)
        visited.add(start_id)

    while queue:
        current = queue.popleft()
        ordered.append(current)
        for neighbor in sorted(adjacency.get(current, [])):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    unreachable = sorted(node_ids - visited)
    ordered.extend(unreachable)
    return ordered


def assemble(extraction: ExtractionResult, ordering: OrderingResult) -> dict:
    nodes, ref_to_id = _dedupe(extraction.activities)

    edges: list[dict] = []
    seen_edges: set[tuple[str, str, str | None]] = set()
    dropped_edges: list[dict] = []

    for e in ordering.edges:
        src = ref_to_id.get(e.source_ref)
        tgt = ref_to_id.get(e.target_ref)
        if src is None or tgt is None:
            dropped_edges.append({"reason": "unresolved ref", "edge": e.model_dump()})
            continue
        if src == tgt:
            dropped_edges.append({"reason": "self-loop", "edge": e.model_dump()})
            continue

        key = (src, tgt, e.condition)
        if key in seen_edges:
            continue
        seen_edges.add(key)

        edges.append(
            {
                "source": src,
                "target": tgt,
                "condition": e.condition,
                "default": e.is_default_branch,
                "grounded": bool(e.quote),
                "quote": e.quote,
                "inferred": e.inferred,
            }
        )

    start_id = ref_to_id.get(ordering.start_ref)
    terminal_ids = sorted({ref_to_id[r] for r in ordering.terminal_refs if r in ref_to_id})

    node_ids = set(nodes.keys())
    ordered_ids = _canonical_order(start_id, node_ids, edges) if start_id else sorted(node_ids)

    return {
        "nodes": [
            {
                "id": nid,
                "label": nodes[nid].label,
                "type": nodes[nid].type,
                "quote": nodes[nid].quote,
                "grounded": nodes[nid].grounded,
                "note": nodes[nid].note,
            }
            for nid in ordered_ids
        ],
        "edges": sorted(edges, key=lambda e: (e["source"], e["target"], e["condition"] or "")),
        "start": start_id,
        "terminals": terminal_ids,
        "dropped_edges": dropped_edges,
    }

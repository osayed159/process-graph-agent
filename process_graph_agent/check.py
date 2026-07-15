from __future__ import annotations

import networkx as nx
from rapidfuzz import fuzz

GROUNDING_FUZZY_THRESHOLD = 85


def check_structure(graph: dict) -> list[dict]:
    problems: list[dict] = []

    node_ids = {n["id"] for n in graph["nodes"]}
    G = nx.DiGraph()
    G.add_nodes_from(node_ids)

    for e in graph["edges"]:
        if e["source"] not in node_ids or e["target"] not in node_ids:
            problems.append(
                {"type": "dangling_edge", "detail": f"{e['source']} -> {e['target']}"}
            )
            continue
        G.add_edge(e["source"], e["target"])

    start = graph.get("start")
    if not start:
        problems.append({"type": "no_start", "detail": "no start node identified"})
    elif start not in node_ids:
        problems.append({"type": "invalid_start", "detail": f"start '{start}' is not a known node"})
    else:
        reachable = nx.descendants(G, start) | {start}
        unreachable = node_ids - reachable
        for nid in sorted(unreachable):
            problems.append({"type": "unreachable_node", "detail": nid})

    terminals = graph.get("terminals") or []
    if not terminals:
        problems.append({"type": "no_terminal", "detail": "no terminal node identified"})
    else:
        for t in terminals:
            if t not in node_ids:
                problems.append({"type": "invalid_terminal", "detail": t})

    return problems


def _is_grounded(quote: str | None, transcript: str) -> bool:
    if not quote:
        return False
    if quote in transcript:
        return True
    return fuzz.partial_ratio(quote, transcript) >= GROUNDING_FUZZY_THRESHOLD


def check_grounding(graph: dict) -> list[dict]:
    problems: list[dict] = []

    for n in graph["nodes"]:
        if not n["grounding_verified"]:
            problems.append({"type": "ungrounded_node", "detail": n["id"]})

    for e in graph["edges"]:
        if not e["grounding_verified"]:
            problems.append(
                {"type": "ungrounded_edge", "detail": f"{e['source']} -> {e['target']}"}
            )

    return problems


def apply_grounding_flags(graph: dict, transcript: str) -> dict:
    for n in graph["nodes"]:
        n["grounding_verified"] = _is_grounded(n.get("quote"), transcript)

    for e in graph["edges"]:
        e["grounding_verified"] = e.get("inferred", False) or _is_grounded(e.get("quote"), transcript)

    return graph


def run_checks(graph: dict, transcript: str) -> dict:
    graph = apply_grounding_flags(graph, transcript)
    structural_problems = check_structure(graph)
    grounding_problems = check_grounding(graph)

    graph["validation"] = {
        "passed": not structural_problems and not grounding_problems,
        "structural_problems": structural_problems,
        "grounding_problems": grounding_problems,
    }
    return graph

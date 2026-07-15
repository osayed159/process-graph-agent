from __future__ import annotations

import os

import anthropic


def get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Export it before running the pipeline, e.g.\n"
            "  export ANTHROPIC_API_KEY=sk-ant-...\n"
            "(PowerShell: $env:ANTHROPIC_API_KEY = 'sk-ant-...')"
        )
    return anthropic.Anthropic(api_key=api_key)

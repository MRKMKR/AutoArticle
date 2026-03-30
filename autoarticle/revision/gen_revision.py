#!/usr/bin/env python3
"""
Rewrite a section from a revision brief or evaluation results.

Usage:
    python gen_revision.py <section_num> [--brief briefs/s01.md] [--dimension clarity|conciseness|technical]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from autoarticle.utils.config import load_config

import httpx


SYSTEM_PROMPT = """You are an expert technical writer. Rewrite the specified section based on the revision brief.

Rules:
- Follow the revision instructions exactly
- Preserve facts and technical accuracy
- Only change what the brief asks to change
- Maintain voice and tone from voice.md
- Do not introduce new content unless the brief asks for it
"""


def build_prompt(section_num: int, brief: str, dimension: str) -> str:
    """Build the revision prompt."""
    section_path = Path(f"sections/section_{section_num:02d}.md")
    if not section_path.exists():
        raise FileNotFoundError(f"Section not found: {section_path}")

    section_text = section_path.read_text()

    # Load context
    ctx_parts = []
    for fname in ["seed.txt", "outline.md", "voice.md"]:
        p = Path(fname)
        if p.exists():
            ctx_parts.append(f"=== {fname} ===\n{p.read_text()[:2000]}")

    # Load cuts if available
    cuts_path = Path(f"edit_logs/section_{section_num:02d}_cuts.json")
    cuts_text = ""
    if cuts_path.exists():
        import json
        cuts = json.loads(cuts_path.read_text())
        cuts_text = f"\n=== Cuts to apply ===\n{json.dumps(cuts.get('cuts', [])[:10], indent=2)}"

    prompt = f"""Rewrite section {section_num} based on this revision brief.

## Revision Brief

{brief}

## Dimension to focus on: {dimension}

## Current section text

{section_text}

## Context

{{ctx}}"""


def call_llm(prompt: str, config) -> str:
    client = httpx.Client(timeout=120)
    response = client.post(
        f"{config.api_base_url}/v1/messages",
        headers={
            "x-api-key": config.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": config.writer_model,
            "max_tokens": 1536,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    if response.status_code != 200:
        raise RuntimeError(f"API error: {response.status_code} {response.text}")
    return response.json()["content"][0]["text"]


def generate_revision(
    section_num: int, brief: str, dimension: str, output_path: Path, config
) -> None:
    section_path = Path(f"sections/section_{section_num:02d}.md")
    if not section_path.exists():
        raise FileNotFoundError(f"Section not found: {section_path}")

    section_text = section_path.read_text()

    # Load context
    ctx_parts = []
    for fname in ["seed.txt", "outline.md", "voice.md"]:
        p = Path(fname)
        if p.exists():
            ctx_parts.append(f"=== {fname} ===\n{p.read_text()[:2000]}")

    # Load cuts if available
    cuts_path = Path(f"edit_logs/section_{section_num:02d}_cuts.json")
    cuts_text = ""
    if cuts_path.exists():
        import json
        cuts = json.loads(cuts_path.read_text())
        high_cuts = [c for c in cuts.get("cuts", []) if c.get("severity") == "high"]
        if high_cuts:
            cuts_text = f"\n=== High-severity cuts to apply ===\n{json.dumps(high_cuts, indent=2)}"

    prompt = f"""Rewrite section {section_num} based on this revision brief.

## Revision Brief

{brief}

## Dimension to focus on: {dimension}

## Current section text

{section_text}

## Context

{chr(10).join(ctx_parts)}
{cuts_text}

---

Rewrite the section following the brief instructions. Output ONLY the revised section text — no headers, no markers.
"""

    print(f"Rewriting section {section_num} (focus: {dimension})...")
    revised = call_llm(prompt, config)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(revised)
    print(f"Revised section written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Rewrite section from revision brief")
    parser.add_argument("section_num", type=int, help="Section number to revise")
    parser.add_argument("--brief", help="Path to revision brief file")
    parser.add_argument(
        "--dimension",
        default="clarity",
        choices=["clarity", "conciseness", "technical", "sources", "tone", "slop"],
        help="Dimension to focus on",
    )
    parser.add_argument("--output", help="Output file (default: sections/section_NN.md)")
    parser.add_argument(
        "--auto",
        help="Auto-generate brief from evaluation results",
        choices=["clarity", "conciseness", "technical", "sources", "tone", "slop"],
    )
    args = parser.parse_args()

    config = load_config()
    section_num = args.section_num
    output_path = Path(args.output) if args.output else Path(f"sections/section_{section_num:02d}.md")

    if args.brief:
        brief = Path(args.brief).read_text()
    elif args.auto:
        # Auto-generate brief from weakest dimension
        brief = f"""Focus revision on the {args.auto} dimension.
        Review the current section and revise specifically to improve {args.auto}.
        Apply any high-severity cuts identified in the adversarial edit pass first.
        Then rewrite for the targeted dimension."""
    else:
        brief = f"""General revision: improve the {args.dimension} dimension.
        Review the current section and revise to improve {args.dimension}."""

    generate_revision(section_num, brief, args.dimension, output_path, config)


if __name__ == "__main__":
    main()

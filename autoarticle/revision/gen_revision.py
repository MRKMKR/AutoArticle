#!/usr/bin/env python3
"""
Rewrite a section from a revision brief or auto-generated note.

Usage:
    python gen_revision.py <section_num> [--brief briefs/s01.md]
    python gen_revision.py <section_num> --auto <dimension>
    python gen_revision.py <section_num> --auto conciseness --strength gentle
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from autoarticle.utils.api import api_post


def get_seed_setting(key: str, default: str = "") -> str:
    """Read a setting from seed.txt."""
    seed_p = Path("seed.txt")
    if not seed_p.exists():
        return default
    for line in seed_p.read_text().splitlines():
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip()
    return default


SYSTEM = """You are an expert technical writer. Rewrite the section based on the revision brief.

Rules:
- Follow the revision instructions exactly
- Preserve facts and technical accuracy
- Only change what the brief asks to change
- Maintain voice and tone from voice.md
- Do not introduce new content unless asked
- Do NOT add citations, references, or source attributions unless the article explicitly includes sources
- Output ONLY the revised section — no headers, no markers"""


# Strength-specific brief modifiers
STRENGTH_BRIEF = {
    "gentle": (
        "IMPORTANT — gentle revision mode: Make minimal, targeted changes. "
        "Preserve as much of the original text as possible. Only remove or rewrite "
        "what is clearly harmful. Do not rewrite sentences that are already adequate. "
        "Goal: small, safe improvement, never worse than the original."
    ),
    "aggressive": (
        "AGGRESSIVE revision mode: Apply all cuts and revisions fully. "
        "Do not be reluctant to remove weak content, simplify convoluted sentences, "
        "and cut filler. Prioritise clarity and conciseness even if it means "
        "significant restructuring. Aim for high-quality output over preserving original phrasing."
    ),
}


def main():
    parser = argparse.ArgumentParser(description="Rewrite section from revision brief")
    parser.add_argument("section_num", type=int)
    parser.add_argument("--brief", help="Path to revision brief file")
    parser.add_argument("--auto", choices=["clarity", "conciseness", "technical", "sources", "tone", "slop"],
                        help="Auto-generate brief from weakest dimension")
    parser.add_argument("--strength", choices=["gentle", "aggressive"], default=None,
                        help="How aggressively to revise (default: gentle, or seed.txt revision_strength)")
    parser.add_argument("--output", help="Output file (default: sections/section_NN.md)")
    args = parser.parse_args()

    # Resolve strength: CLI arg > seed.txt > default
    strength = strength or get_seed_setting("revision_strength", "gentle")
    if strength not in ("gentle", "aggressive"):
        strength = "gentle"

    section_num = args.section_num
    output_path = Path(args.output) if args.output else Path(f"sections/section_{section_num:02d}.md")
    section_path = Path(f"sections/section_{section_num:02d}.md")

    if not section_path.exists():
        print(f"Error: section not found: {section_path}")
        sys.exit(1)

    section_text = section_path.read_text()

    if args.brief:
        brief = Path(args.brief).read_text()
        dimension = "general"
    elif args.auto:
        dimension = args.auto
        if dimension == "conciseness":
            if strength == "gentle":
                brief = (
                    "Gently improve conciseness. Apply only the highest-severity cuts from the adversarial edit pass. "
                    "Trim unnecessary words and remove genuinely redundant phrases, but preserve all substantive content. "
                    "Target ~10-20% word reduction at most. Do not rewrite sentences that are already clear and brief."
                )
            else:
                brief = (
                    "Aggressively improve conciseness. Apply all recommended cuts from the adversarial edit pass. "
                    "Remove filler, weak qualifiers, and redundant phrases without mercy. "
                    "Target 20-40% word reduction. Prefer short sentences. Remove anything that doesn't add value."
                )
        else:
            brief = f"Focus revision on the {dimension} dimension. Review the current section and revise specifically to improve {dimension}. Apply high-severity cuts from the adversarial edit pass first."
    else:
        dimension = "general"
        brief = f"General revision: improve overall quality while preserving all facts."

    # Append strength note to brief
    brief = f"{brief}\n\n{STRENGTH_BRIEF[strength]}"

    # Load cuts — gentle uses only high, aggressive uses high + medium
    cuts_text = ""
    cuts_path = Path(f"edit_logs/section_{section_num:02d}_cuts.json")
    if cuts_path.exists():
        cuts = json.loads(cuts_path.read_text())
        if strength == "gentle":
            # Only high-severity cuts in gentle mode
            relevant_cuts = [c for c in cuts.get("cuts", []) if c.get("severity") == "high"]
        else:
            # All cuts in aggressive mode
            relevant_cuts = [c for c in cuts.get("cuts", []) if c.get("severity") in ("high", "medium")]
        if relevant_cuts:
            cuts_text = "\n=== Recommended cuts to apply ===\n" + json.dumps(relevant_cuts, indent=2)

    # Load context
    ctx_parts = []
    for fname in ["seed.txt", "outline.md", "voice.md"]:
        p = Path(fname)
        if p.exists():
            ctx_parts.append(f"=== {fname} ===\n{p.read_text()[:1500]}")
    context = "\n\n".join(ctx_parts)

    # Check include_sources from seed
    include_sources = "none"
    seed_p = Path("seed.txt")
    if seed_p.exists():
        for line in seed_p.read_text().splitlines():
            if line.startswith("include_sources:"):
                include_sources = line.split(":", 1)[1].strip()
                break
    if include_sources == "none":
        context += "\n\n[IMPORTANT] This article has include_sources: none — do NOT add any citations, references, or source attributions. If you need to make a factual claim, use your existing knowledge without citing sources."

    prompt = f"""Rewrite section {section_num} based on this revision brief.

## Revision Brief
{brief}

## Dimension: {dimension}

## Current section
{section_text}

## Context
{context}
{cuts_text}

---

Output ONLY the revised section text."""

    print(f"Rewriting section {section_num} (focus: {dimension}, strength: {strength})...")
    revised = api_post(prompt, system=SYSTEM, max_tokens=2048)

    output_path.write_text(revised)
    print(f"Written to: {output_path}")


if __name__ == "__main__":
    main()

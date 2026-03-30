#!/usr/bin/env python3
"""
Rewrite a section from a revision brief or auto-generated note.

Usage:
    python gen_revision.py <section_num> [--brief briefs/s01.md]
    python gen_revision.py <section_num> --auto <dimension>
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from autoarticle.utils.api import api_post


SYSTEM = """You are an expert technical writer. Rewrite the section based on the revision brief.

Rules:
- Follow the revision instructions exactly
- Preserve facts and technical accuracy
- Only change what the brief asks to change
- Maintain voice and tone from voice.md
- Do not introduce new content unless asked
- Output ONLY the revised section — no headers, no markers"""


def main():
    parser = argparse.ArgumentParser(description="Rewrite section from revision brief")
    parser.add_argument("section_num", type=int)
    parser.add_argument("--brief", help="Path to revision brief file")
    parser.add_argument("--auto", choices=["clarity", "conciseness", "technical", "sources", "tone", "slop"],
                        help="Auto-generate brief from weakest dimension")
    parser.add_argument("--output", help="Output file (default: sections/section_NN.md)")
    args = parser.parse_args()

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
        brief = f"Focus revision on the {dimension} dimension. Review the current section and revise specifically to improve {dimension}. Apply high-severity cuts from the adversarial edit pass first."
    else:
        dimension = "general"
        brief = f"General revision: improve overall quality while preserving all facts."

    # Load cuts if available
    cuts_text = ""
    cuts_path = Path(f"edit_logs/section_{section_num:02d}_cuts.json")
    if cuts_path.exists():
        cuts = json.loads(cuts_path.read_text())
        high_cuts = [c for c in cuts.get("cuts", []) if c.get("severity") == "high"]
        if high_cuts:
            cuts_text = "\n=== High-severity cuts to apply ===\n" + json.dumps(high_cuts, indent=2)

    # Load context
    ctx_parts = []
    for fname in ["seed.txt", "outline.md", "voice.md"]:
        p = Path(fname)
        if p.exists():
            ctx_parts.append(f"=== {fname} ===\n{p.read_text()[:1500]}")
    context = "\n\n".join(ctx_parts)

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

    print(f"Rewriting section {section_num} (focus: {dimension})...")
    revised = api_post(prompt, system=SYSTEM, max_tokens=1536)

    output_path.write_text(revised)
    print(f"Written to: {output_path}")


if __name__ == "__main__":
    main()

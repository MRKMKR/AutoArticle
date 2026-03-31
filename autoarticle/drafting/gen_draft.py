#!/usr/bin/env python3
"""
Draft a single section using the writer model.

Usage:
    python gen_draft.py <section_num> [--output sections/section_NN.md]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from autoarticle.utils.api import api_post


SYSTEM = """You are an expert technical writer. Draft a single section of an article following the outline, voice guide, and context provided.

Rules:
- Target length specified in the outline section
- Follow voice.md tone and style exactly
- Active voice, 2-4 sentence paragraphs
- Define technical terms on first use
- No Tier 1 banned words (delve, utilize, leverage, facilitate, elucidate, embark, endeavor, encompass, multifaceted, tapestry, testament, paradigm, synergy, holistic, catalyze, juxtapose, realm, landscape, myriad, plethora)
- Do not use claim inflation (revolutionary, groundbreaking, game-changing)
- Be specific — numbers, names, exact details
- Write ONLY this section — no intros/outros/structure markers
- Do NOT invent or add any URLs, citations, references, or source attributions"""


def load_context(section_num: int) -> str:
    """Load context files for drafting."""
    ctx_parts = []
    for fname in ["seed.txt", "outline.md", "voice.md", "sources.md"]:
        path = Path(fname)
        if path.exists():
            ctx_parts.append(f"=== {fname} ===\n{path.read_text()[:2000]}")

    # Previous section for continuity
    prev = Path(f"sections/section_{section_num-1:02d}.md")
    if prev.exists():
        words = prev.read_text().split()
        excerpt = " ".join(words[-400:])
        ctx_parts.append(f"=== previous section (last 400 words) ===\n{excerpt}")

    # Next section outline
    outline_path = Path("outline.md")
    if outline_path.exists():
        lines = outline_path.read_text().split("\n")
        for i, line in enumerate(lines):
            if line.startswith(f"## {section_num + 1}. "):
                next_lines = []
                for j in range(i + 1, min(i + 15, len(lines))):
                    if lines[j].startswith("## "):
                        break
                    next_lines.append(lines[j])
                if next_lines:
                    ctx_parts.append(f"=== next section outline ===\n" + "\n".join(next_lines))
                break

    return "\n\n".join(ctx_parts)


def extract_section_outline(outline_text: str, section_num: int) -> str:
    """Extract the outline block for a specific section number.

    Standard format: "## N. Title" (e.g., "## 1. Motivation: From Blank Page").
    Also handles legacy formats (belt-and-braces):
    - "## Section N: Title"
    - "## N: Title"
    - "## Title" (unnumbered — section_num = nth such heading)
    """
    import re

    # Collect all top-level ## headings (not ###)
    headings = []
    for line in outline_text.split("\n"):
        m = re.match(r"^(#{2,3}) (.*)", line)
        if not m:
            continue
        level, title = m.groups()
        if level == "##":  # Only top-level headings
            headings.append(title.strip())

    if section_num > len(headings):
        return ""

    target_title = headings[section_num - 1]

    # Now extract content between this heading and the next ## heading
    lines = outline_text.split("\n")
    in_section = False
    section_lines = []

    for line in lines:
        if line.lstrip("#").strip() == target_title and line.startswith("## "):
            if in_section:
                break
            in_section = True
            section_lines.append(line)
        elif in_section:
            if re.match(r"^## .", line) or re.match(r"^# .", line):
                break
            section_lines.append(line)

    return "\n".join(section_lines).strip()


def main():
    parser = argparse.ArgumentParser(description="Draft a single section")
    parser.add_argument("section_num", type=int, help="Section number to draft")
    parser.add_argument("--output", help="Output file path")
    args = parser.parse_args()

    section_num = args.section_num
    ctx = load_context(section_num)

    outline_text = Path("outline.md").read_text() if Path("outline.md").exists() else ""
    section_outline = extract_section_outline(outline_text, section_num)

    if not section_outline:
        print(f"Error: Section {section_num} not found in outline.md")
        sys.exit(1)

    prompt = f"""Draft section {section_num} of the article.

## This Section's Outline

{section_outline}

## Context

{ctx}

---

Write ONLY the section content. No headers, no markers. Just the prose."""

    print(f"Drafting section {section_num}...")
    draft = api_post(prompt, system=SYSTEM, max_tokens=1536)

    output_path = Path(args.output) if args.output else Path(f"sections/section_{section_num:02d}.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(draft)
    print(f"Section written to: {output_path}")


if __name__ == "__main__":
    main()

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

from autoarticle.utils.config import load_config

import httpx


def load_context(section_num: int) -> dict:
    """Load all context files for drafting."""
    ctx = {}

    for fname in ["seed.txt", "outline.md", "voice.md", "sources.md"]:
        path = Path(fname)
        if path.exists():
            ctx[fname] = path.read_text()

    # Load previous section for continuity
    sections_dir = Path("sections")
    if section_num > 1:
        prev = sections_dir / f"section_{section_num-1:02d}.md"
        if prev.exists():
            ctx["previous_section"] = prev.read_text()
            # Last ~500 words of previous section
            words = prev.read_text().split()
            ctx["previous_excerpt"] = " ".join(words[-500:])

    # Load next section outline
    if Path("outline.md").exists():
        outline = Path("outline.md").read_text()
        # Extract next section heading from outline
        lines = outline.split("\n")
        for i, line in enumerate(lines):
            if line.startswith(f"## Section {section_num + 1}"):
                # Collect next section content
                next_section_lines = []
                for j in range(i + 1, min(i + 20, len(lines))):
                    if lines[j].startswith("## "):
                        break
                    next_section_lines.append(lines[j])
                ctx["next_section_outline"] = "\n".join(next_section_lines)
                break

    return ctx


SYSTEM_PROMPT = """You are an expert technical writer. Draft a single section of an article following the outline, voice guide, and context provided.

Rules:
- Target length specified in the outline section
- Follow voice.md tone and style exactly
- Active voice, 2-4 sentence paragraphs
- Define technical terms on first use
- No Tier 1 banned words (delve, utilize, leverage, facilitate, elucidate, embark, endeavor, encompass, multifaceted, tapestry, testament, paradigm, synergy, holistic, catalyze, juxtapose, realm, landscape, myriad, plethora)
- Do not use claim inflation (revolutionary, groundbreaking, game-changing)
- Be specific — numbers, names, exact details
- Write ONLY this section — no intros/outros/structure markers
"""


def call_llm(prompt: str, config) -> str:
    client = httpx.Client(timeout=60)
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


def main():
    parser = argparse.ArgumentParser(description="Draft a single section")
    parser.add_argument("section_num", type=int, help="Section number to draft")
    parser.add_argument("--output", help="Output file path")
    args = parser.parse_args()

    section_num = args.section_num
    config = load_config()
    ctx = load_context(section_num)

    # Build prompt
    outline = ctx.get("outline.md", "")
    voice = ctx.get("voice.md", "")
    seed = ctx.get("seed.txt", "")
    sources = ctx.get("sources.md", "")

    # Extract this section from outline
    section_header = f"## Section {section_num}"
    section_content = ""
    in_section = False
    for line in outline.split("\n"):
        if line.startswith(f"## Section {section_num} "):
            in_section = True
            section_content = line + "\n"
        elif in_section:
            if line.startswith("## "):
                break
            section_content += line + "\n"

    prompt = f"""Draft section {section_num} of the article.

## This Section's Outline

{section_content}

## Voice Guide

{voice}

## Seed / Context

{seed}

## Sources (do not copy directly, use for verification)

{sources}

{ctx.get('previous_excerpt', '') and f"## Previous Section (for continuity)\n{ctx['previous_excerpt']}\n"}
{ctx.get('next_section_outline', '') and f"## Next Section Outline\n{ctx['next_section_outline']}\n"}

---

Write ONLY the section content. No headers, no markers. Just the prose."""


    print(f"Drafting section {section_num}...")
    draft = call_llm(prompt, config)

    output_path = Path(args.output) if args.output else Path(f"sections/section_{section_num:02d}.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(draft)
    print(f"Section written to: {output_path}")


if __name__ == "__main__":
    main()

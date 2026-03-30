#!/usr/bin/env python3
"""
Generate voice.md from seed examples and anti_slop reference.

Usage:
    python gen_voice.py [--seed seed.txt] [--output voice.md]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from autoarticle.utils.api import api_post


SYSTEM = """You are an expert technical writer and writing coach. Analyze the provided seed information and style examples to generate a precise voice guide for an article.

Output a voice.md file with these sections:

# Voice Guide

## Tone
One paragraph describing the target tone. Be specific — not "professional" but "confident but not arrogant, willing to say what others won't, direct in a way that respects the reader's intelligence."

## Audience Calibration
How does tone shift for the target audience? What vocabulary level, explanation depth, and assumption level is appropriate?

## Vocabulary
- **Use:** specific, precise terms (e.g., "240MHz ESP32" not "fast chip")
- **Avoid:** vague superlatives, jargon without definition, unnecessary foreign phrases

## Sentence Style
- Paragraph target: 2-4 sentences max
- Prefer active voice
- One idea per sentence
- Technical terms defined on first use

## What to Avoid
Specific things to never do in this article (based on the anti-slop reference and style examples).

## Example Passages
Two example passages showing the target voice — one from the provided examples (if available) analyzed, and one new passage you write in the target style."""


def main():
    parser = argparse.ArgumentParser(description="Generate voice guide from seed")
    parser.add_argument("--seed", default="seed.txt")
    parser.add_argument("--output", default="voice.md")
    args = parser.parse_args()

    seed_path = Path(args.seed)
    if not seed_path.exists():
        print(f"Error: seed file not found: {seed_path}")
        sys.exit(1)

    seed_content = seed_path.read_text()

    # Read anti_slop for context
    anti_slop_path = Path(__file__).parent.parent.parent / "refs" / "anti_slop.md"
    anti_slop = anti_slop_path.read_text() if anti_slop_path.exists() else ""

    prompt = f"""Analyze these seed bullets and style examples to create a voice guide for the article.

## Seed

{seed_content}

## Anti-Slop Reference (things to definitely avoid)

{anti_slop[:3000]}

---

Generate the voice guide following the format in the system prompt. Be specific and actionable — avoid generic advice."""

    print("Generating voice guide...")
    voice = api_post(prompt, system=SYSTEM, max_tokens=1536)

    output_path = Path(args.output)
    output_path.write_text(voice)
    print(f"Voice guide written to: {output_path}")


if __name__ == "__main__":
    main()

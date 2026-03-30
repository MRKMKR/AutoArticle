#!/usr/bin/env python3
"""
Generate voice.md from seed examples and anti_slop reference.

Usage:
    python gen_voice.py [--seed seed.txt] [--output voice.md]
Output: voice.md
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from autoarticle.utils.config import load_config

import httpx


SYSTEM_PROMPT = """You are an expert technical writer and writing coach. Analyze the provided seed information and style examples to generate a precise voice guide for an article.

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
Two example passages showing the target voice — one from the provided examples (if available) analyzed, and one new passage you write in the target style.
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
    parser = argparse.ArgumentParser(description="Generate voice guide from seed")
    parser.add_argument("--seed", default="seed.txt")
    parser.add_argument("--output", default="voice.md")
    args = parser.parse_args()

    seed_path = Path(args.seed)
    if not seed_path.exists():
        print(f"Error: seed file not found: {seed_path}")
        sys.exit(1)

    seed_content = seed_path.read_text()
    config = load_config()

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
    voice = call_llm(prompt, config)

    output_path = Path(args.output)
    output_path.write_text(voice)
    print(f"Voice guide written to: {output_path}")


if __name__ == "__main__":
    main()

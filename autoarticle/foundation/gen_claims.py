#!/usr/bin/env python3
"""
Generate claims.json from outline.

Extracts structured factual claims from the outline for tracking and verification.

Usage:
    python gen_claims.py [--outline outline.md] [--output claims.json]
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from autoarticle.utils.api import api_post


SYSTEM = """You are a research analyst. Given an article outline, extract every factual claim into a structured JSON list.

Output ONLY valid JSON — no markdown code blocks, no explanation. The JSON should be an array of claim objects.

Each claim object:
{
  "id": "c01",
  "section": "Intro",
  "text": "The ESP32-S3 runs at up to 240MHz",
  "needs_verification": true,
  "source_hint": "Espressif ESP32-S3 datasheet",
  "verified": false,
  "source": null
}"""


def main():
    parser = argparse.ArgumentParser(description="Extract claims to JSON")
    parser.add_argument("--outline", default="outline.md")
    parser.add_argument("--output", default="claims.json")
    args = parser.parse_args()

    outline_path = Path(args.outline)
    if not outline_path.exists():
        print(f"Error: outline not found: {outline_path}")
        sys.exit(1)

    outline = outline_path.read_text()

    prompt = f"""Extract all factual claims from this outline into JSON.

{outline}

Output ONLY a JSON array. No markdown, no explanation."""

    print("Extracting claims...")
    raw = api_post(prompt, system=SYSTEM, max_tokens=2048)

    # Strip markdown code blocks if present
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"```\s*$", "", raw)
    raw = raw.strip()

    try:
        claims = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Warning: JSON parse failed: {e}")
        print(f"Raw output:\n{raw[:500]}")
        claims = []

    output_path = Path(args.output)
    output_path.write_text(json.dumps(claims, indent=2))
    print(f"Claims written to: {output_path} ({len(claims)} claims)")


if __name__ == "__main__":
    main()

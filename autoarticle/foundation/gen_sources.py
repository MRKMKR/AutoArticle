#!/usr/bin/env python3
"""
Generate sources.md from outline and seed.

Identifies claims in the outline that need external verification.

Usage:
    python gen_sources.py [--outline outline.md] [--seed seed.txt] [--output sources.md]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from autoarticle.utils.api import api_post


SYSTEM = """You are a research librarian. Given an article outline, identify every factual claim that needs external verification.

Output a sources.md file with this format:

# Sources

## Claims Requiring Verification

For each claim, note what kind of source is needed. Do NOT fetch sources — just identify what's needed.

| Section | Claim | Source Type Needed | Hint |
|---------|-------|-------------------|------|
| Intro | ESP32 runs at 240MHz | Official spec | Espressif datasheet |
| ... | ... | ... | ... |

## Source Priority
- **Primary:** Official documentation, primary research papers
- **Secondary:** Expert reviews, authoritative secondary sources
- **Tertiary:** General reference, news articles

## Known Good Sources
URLs or references you've already verified are credible."""


def main():
    parser = argparse.ArgumentParser(description="Generate sources list from outline")
    parser.add_argument("--outline", default="outline.md")
    parser.add_argument("--seed", default="seed.txt")
    parser.add_argument("--output", default="sources.md")
    args = parser.parse_args()

    outline_path = Path(args.outline)
    seed_path = Path(args.seed)

    if not outline_path.exists():
        print(f"Error: outline not found: {outline_path}")
        sys.exit(1)

    outline = outline_path.read_text()
    seed = seed_path.read_text() if seed_path.exists() else ""

    prompt = f"""Given this article outline and seed, identify every factual claim that needs external verification.

## Outline

{outline}

## Seed (article requirements)

{seed}

---

List all claims that need a source. Categorize by:
- Primary source needed (official docs, specs, primary research)
- Secondary source needed (expert analysis, reviews)
- No source needed (opinion, common knowledge, or your own experience)

Be specific — "240MHz clock speed" needs a spec sheet. "Most developers prefer Python" needs a survey."""

    print("Analyzing claims requiring verification...")
    sources = api_post(prompt, system=SYSTEM, max_tokens=1536)

    output_path = Path(args.output)
    output_path.write_text(sources)
    print(f"Sources written to: {output_path}")


if __name__ == "__main__":
    main()

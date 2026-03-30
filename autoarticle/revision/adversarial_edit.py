#!/usr/bin/env python3
"""
Adversarial editing pass: ask the judge to identify cuts to make text more concise.

For each section, asks: "what would you cut?" and classifies cuts by type.

Usage:
    python adversarial_edit.py <section_num|all> [--target 15] [--output edit_logs/]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from autoarticle.utils.config import load_config
from autoarticle.utils.state import load_state

import httpx


CUT_CLASSIFICATIONS = [
    "OVER-EXPLAIN",
    "REDUNDANT",
    "WEAK_EVIDENCE",
    "VAGUE",
    "FILLER",
    "OFF-TOPIC",
    "REPETITION",
]


SYSTEM_PROMPT = f"""You are an expert editor. Analyze text and identify cuts to make it more concise without losing meaning.

For each cut, classify it as one of:
{CUT_CLASSIFICATIONS}

Rules:
- Aim for the target cut percentage
- Cuts should not remove essential meaning
- Classify each cut precisely
- Return JSON only
"""


def call_adversarial(text: str, target_pct: int, config) -> dict:
    """Ask judge to identify and classify cuts."""
    prompt = f"""Identify cuts to make this text approximately {target_pct}% more concise.

For each cut provide:
- text: the exact text to cut
- classification: one of {CUT_CLASSIFICATIONS}
- severity: high/medium/low (high = definitely cut, low = consider cutting)
- reason: brief justification

Target: {target_pct}% word reduction.

Text:
{text[:6000]}
"""

    client = httpx.Client(timeout=120)
    response = client.post(
        f"{config.api_base_url}/v1/messages",
        headers={
            "x-api-key": config.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": config.judge_model,
            "max_tokens": 1536,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        },
    )

    if response.status_code != 200:
        raise RuntimeError(f"API error: {response.status_code} {response.text}")

    import re
    raw = response.json()["content"][0]["text"]
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"```\s*$", "", raw)
    raw = raw.strip()

    try:
        data = json.loads(raw)
        if isinstance(data, dict) and "cuts" in data:
            return data
        if isinstance(data, list):
            return {"cuts": data}
        return {"cuts": []}
    except json.JSONDecodeError:
        return {"cuts": [], "parse_error": raw[:200]}


def process_file(section_path: Path, target_pct: int, config, output_dir: Path) -> dict:
    """Process a single section file."""
    text = section_path.read_text()
    original_words = len(text.split())

    result = call_adversarial(text, target_pct, config)

    cuts = result.get("cuts", [])
    cut_texts = [c.get("text", "") for c in cuts if c.get("text")]
    cut_words = sum(len(ct.split()) for ct in cut_texts)
    actual_pct = (cut_words / original_words * 100) if original_words > 0 else 0

    output = {
        "file": str(section_path),
        "original_words": original_words,
        "target_pct": target_pct,
        "cuts_found": len(cuts),
        "cut_words": cut_words,
        "actual_pct": round(actual_pct, 1),
        "cuts": cuts,
    }

    # Save to edit_logs
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = section_path.stem
    out_path = output_dir / f"{slug}_cuts.json"
    out_path.write_text(json.dumps(output, indent=2))

    return output


def print_summary(results: list) -> None:
    """Print a summary of all cuts."""
    print(f"\n{'='*50}")
    print("ADVERSARIAL EDIT SUMMARY")
    print(f"{'='*50}")

    for r in results:
        fname = Path(r["file"]).name
        print(f"\n  {fname}:")
        print(f"    Words: {r['original_words']} → target -{r['target_pct']}%")
        print(f"    Cuts found: {r['cuts_found']} ({r['cut_words']} words, {r['actual_pct']:.1f}% actual)")

        # Group by classification
        by_class = {}
        for cut in r.get("cuts", []):
            cls = cut.get("classification", "UNKNOWN")
            by_class.setdefault(cls, []).append(cut)

        for cls, cls_cuts in sorted(by_class.items()):
            high = [c for c in cls_cuts if c.get("severity") == "high"]
            print(f"    {cls}: {len(cls_cuts)} total ({len(high)} high severity)")

    total_cuts = sum(r["cuts_found"] for r in results)
    total_words = sum(r["cut_words"] for r in results)
    print(f"\n  TOTAL: {total_cuts} cuts, {total_words} words")
    print(f"\n  Cut files written to: edit_logs/")


def main():
    parser = argparse.ArgumentParser(description="Adversarial edit — find and classify cuts")
    parser.add_argument("target", help="Section number (1, 2, ...) or 'all'")
    parser.add_argument("--target-pct", type=int, default=15, help="Target cut percentage (default: 15)")
    parser.add_argument("--output", default="edit_logs", help="Output directory")
    args = parser.parse_args()

    config = load_config()
    output_dir = Path(args.output)

    if args.target == "all":
        sections_dir = Path("sections")
        if not sections_dir.exists():
            print("Error: sections/ directory not found")
            sys.exit(1)
        section_files = sorted(sections_dir.glob("section_*.md"))
        if not section_files:
            print("Error: no section files found in sections/")
            sys.exit(1)
        print(f"Processing all {len(section_files)} sections...")
        results = []
        for sf in section_files:
            print(f"  Processing {sf.name}...")
            r = process_file(sf, args.target_pct, config, output_dir)
            results.append(r)
        print_summary(results)

    else:
        try:
            section_num = int(args.target)
        except ValueError:
            print(f"Error: '{args.target}' is not a number or 'all'")
            sys.exit(1)

        section_path = Path(f"sections/section_{section_num:02d}.md")
        if not section_path.exists():
            print(f"Error: section not found: {section_path}")
            sys.exit(1)

        print(f"Processing section {section_num}...")
        result = process_file(section_path, args.target_pct, config, output_dir)
        print_summary([result])

        # Also print cuts in detail
        cuts = result.get("cuts", [])
        if cuts:
            print(f"\nTop cuts:")
            high = [c for c in cuts if c.get("severity") == "high"][:5]
            for i, cut in enumerate(high, 1):
                print(f"  {i}. [{cut.get('classification')}] \"{cut.get('text', '')[:60]}...\"")
                print(f"     Reason: {cut.get('reason', '')}")


if __name__ == "__main__":
    main()

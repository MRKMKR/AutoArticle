#!/usr/bin/env python3
"""
Adversarial editing pass: find classified cuts per section.

Usage:
    python adversarial_edit.py <section_num|all> [--target-pct 15] [--output edit_logs/]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from autoarticle.utils.api import api_post


CUT_CLASSIFICATIONS = [
    "OVER-EXPLAIN", "REDUNDANT", "WEAK_EVIDENCE",
    "VAGUE", "FILLER", "OFF-TOPIC", "REPETITION",
]


SYSTEM = f"""You are an expert editor. Analyze text and identify cuts to make it more concise without losing meaning.

For each cut, provide:
- text: exact text to cut
- classification: one of {CUT_CLASSIFICATIONS}
- severity: high/medium/low
- reason: brief justification

Return ONLY valid JSON:
{{"cuts": [{{"text": "...", "classification": "...", "severity": "high", "reason": "..."}}]}}"""


def parse_json(raw: str) -> dict:
    import re
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


def process_file(section_path: Path, target_pct: int, output_dir: Path) -> dict:
    text = section_path.read_text()
    orig_words = len(text.split())

    prompt = f"""Identify cuts to make this text approximately {target_pct}% more concise.
For each cut provide text, classification, severity, and reason.

Text:
{text[:6000]}"""

    raw = api_post(prompt, system=SYSTEM, max_tokens=1536)
    result = parse_json(raw)
    cuts = result.get("cuts", [])

    cut_words = sum(len(c.get("text", "").split()) for c in cuts)
    actual_pct = round(cut_words / orig_words * 100, 1) if orig_words > 0 else 0

    output = {
        "file": str(section_path),
        "original_words": orig_words,
        "target_pct": target_pct,
        "cuts_found": len(cuts),
        "cut_words": cut_words,
        "actual_pct": actual_pct,
        "cuts": cuts,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    slug = section_path.stem
    out_path = output_dir / f"{slug}_cuts.json"
    out_path.write_text(json.dumps(output, indent=2))

    return output


def print_summary(results: list) -> None:
    print(f"\n{'='*50}")
    print("ADVERSARIAL EDIT SUMMARY")
    print(f"{'='*50}")
    for r in results:
        fname = Path(r["file"]).name
        print(f"\n  {fname}:")
        print(f"    {r['original_words']} words → -{r['target_pct']}% target, {r['actual_pct']}% actual")
        print(f"    Cuts: {r['cuts_found']} ({r['cut_words']} words)")
        by_cls = {}
        for c in r.get("cuts", []):
            by_cls.setdefault(c.get("classification", "?"), []).append(c)
        for cls, cls_cuts in sorted(by_cls.items()):
            high = [c for c in cls_cuts if c.get("severity") == "high"]
            print(f"    {cls}: {len(cls_cuts)} total ({len(high)} high)")

    total = sum(r["cuts_found"] for r in results)
    twords = sum(r["cut_words"] for r in results)
    print(f"\n  TOTAL: {total} cuts, {twords} words")
    print(f"  Written to: edit_logs/")


def main():
    parser = argparse.ArgumentParser(description="Adversarial edit — find classified cuts")
    parser.add_argument("target", help="Section number or 'all'")
    parser.add_argument("--target-pct", type=int, default=15)
    parser.add_argument("--output", default="edit_logs")
    args = parser.parse_args()

    output_dir = Path(args.output)

    if args.target == "all":
        sections_dir = Path("sections")
        if not sections_dir.exists():
            print("Error: sections/ not found")
            sys.exit(1)
        files = sorted(sections_dir.glob("section_*.md"))
        if not files:
            print("Error: no sections found")
            sys.exit(1)
        print(f"Processing {len(files)} sections...")
        results = [process_file(f, args.target_pct, output_dir) for f in files]
        print_summary(results)
    else:
        try:
            n = int(args.target)
        except ValueError:
            print(f"Error: '{args.target}' not a number or 'all'")
            sys.exit(1)
        section_path = Path(f"sections/section_{n:02d}.md")
        if not section_path.exists():
            print(f"Error: not found: {section_path}")
            sys.exit(1)
        result = process_file(section_path, args.target_pct, output_dir)
        print_summary([result])
        high = [c for c in result["cuts"] if c.get("severity") == "high"][:5]
        if high:
            print(f"\nTop cuts:")
            for i, c in enumerate(high, 1):
                print(f"  {i}. [{c.get('classification')}] \"{c.get('text', '')[:60]}...\"")
                print(f"     {c.get('reason', '')}")


if __name__ == "__main__":
    main()

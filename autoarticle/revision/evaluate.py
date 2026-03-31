#!/usr/bin/env python3
"""
Evaluate article quality across 6 dimensions.

Usage:
    python evaluate.py --phase=foundation
    python evaluate.py --section=N
    python evaluate.py --full
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from autoarticle.utils.api import api_post
from autoarticle.utils.state import load_state


SYSTEM = """You are an expert article evaluator. Score articles on 6 dimensions. Be strict but fair. Rate 0-10 per dimension. Output ONLY valid JSON.

Dimensions:
- clarity: Is every sentence understandable to the target audience without rereading?
- conciseness: Could this lose 20% of words without losing meaning?
- technical: Are technical claims accurate, precise, and correctly scoped?
- sources: Are factual claims supported by credible sources? (N/A if include_sources=none)
- tone: Is the tone consistent and appropriate for the target audience?
- slop: Does this read as natural human writing? Watch for AI tells.

Output format:
{
  "clarity": {"score": 7, "notes": "brief note"},
  "conciseness": {"score": 6, "notes": "brief note"},
  "technical": {"score": 8, "notes": "brief note"},
  "sources": {"score": 7, "notes": "brief note"},
  "tone": {"score": 7, "notes": "brief note"},
  "slop": {"score": 6, "notes": "brief note"},
  "overall": 7,
  "weakest_dimension": "conciseness",
  "suggestions": ["suggestion 1", "suggestion 2"]
}"""


def parse_json_response(raw: str) -> dict:
    """Parse LLM JSON response, stripping markdown."""
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"```\s*$", "", raw)
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "clarity": {"score": 5, "notes": "parse error"},
            "conciseness": {"score": 5, "notes": "parse error"},
            "technical": {"score": 5, "notes": "parse error"},
            "sources": {"score": 5, "notes": "parse error"},
            "tone": {"score": 5, "notes": "parse error"},
            "slop": {"score": 5, "notes": "parse error"},
            "overall": 5,
            "weakest_dimension": "clarity",
            "suggestions": [],
        }


def build_context() -> str:
    """Load planning docs as context."""
    parts = []
    for fname in ["seed.txt", "outline.md", "voice.md", "sources.md"]:
        p = Path(fname)
        if p.exists():
            parts.append(f"=== {fname} ===\n{p.read_text()[:2000]}")
    return "\n\n".join(parts)


def score_text(text: str, context: str) -> dict:
    prompt = f"""Evaluate this article.

## Article Text

{text[:8000]}

## Context

{context[:4000]}"""
    raw = api_post(prompt, system=SYSTEM, max_tokens=1024)
    return parse_json_response(raw)


def score_foundation() -> dict:
    parts = []
    for fname in ["outline.md", "voice.md", "sources.md"]:
        p = Path(fname)
        if p.exists():
            parts.append(f"=== {fname} ===\n{p.read_text()[:3000]}")
    text = "\n\n".join(parts)
    return score_text(text, "Foundation phase: scoring outline, voice, and sources.")


def score_section(section_num: int) -> dict:
    section_path = Path(f"sections/section_{section_num:02d}.md")
    if not section_path.exists():
        raise FileNotFoundError(f"Section not found: {section_path}")

    ctx_parts = []
    for fname in ["seed.txt", "outline.md", "voice.md"]:
        p = Path(fname)
        if p.exists():
            ctx_parts.append(f"=== {fname} ===\n{p.read_text()[:1500]}")

    prev = Path(f"sections/section_{section_num-1:02d}.md")
    nxt = Path(f"sections/section_{section_num+1:02d}.md")
    if prev.exists():
        ctx_parts.append(f"=== previous ===\n{prev.read_text()[:400]}")
    if nxt.exists():
        ctx_parts.append(f"=== next ===\n{nxt.read_text()[:400]}")

    context = "\n\n".join(ctx_parts)
    text = section_path.read_text()
    return score_text(text, context)


def score_full() -> dict:
    from autoarticle.drafting.anti_slop import scan_file

    section_files = sorted(Path("sections").glob("section_*.md"))
    all_text = []
    for sf in section_files:
        all_text.append(f"=== {sf.name} ===\n{sf.read_text()}")

    text = "\n\n".join(all_text)
    context = build_context()

    # Mechanical slop scan
    slop_mechanical = []
    for sf in section_files:
        f = scan_file(sf)
        slop_mechanical.append({
            "file": sf.name,
            "tier1": len(f["tier1"]),
            "tier2": len(f["tier2"]),
            "inflation": len(f["inflation"]),
            "weasel": len(f["weasel"]),
            "passive_ratio": round(f["passive_ratio"], 3),
        })

    scores = score_text(text, context)

    # Adjust slop score mechanically
    total_t1 = sum(s["tier1"] for s in slop_mechanical)
    total_weasel = sum(s["weasel"] for s in slop_mechanical)
    avg_passive = sum(s["passive_ratio"] for s in slop_mechanical) / max(len(slop_mechanical), 1)

    penalty = 0
    if total_t1 > 0:
        penalty += total_t1 * 0.5
    if total_weasel > 2:
        penalty += (total_weasel - 2) * 0.2
    if avg_passive > 0.15:
        penalty += 1.0

    adj = max(0, scores.get("slop", {}).get("score", 7) - penalty)
    scores["slop"]["score"] = round(adj, 1)
    scores["slop"]["notes"] += f" (mech: tier1={total_t1}, weasel={total_weasel}, passive={avg_passive:.0%})"

    # Recompute overall
    dims = ["clarity", "conciseness", "technical", "sources", "tone", "slop"]
    weights = [0.25, 0.15, 0.25, 0.20, 0.10, 0.05]
    total_w = sum(weights)
    scores["overall"] = round(
        sum(scores.get(d, {}).get("score", 6) * w for d, w in zip(dims, weights)) / total_w, 1
    )

    return {"scores": scores, "slop_mechanical": slop_mechanical, "files_scanned": len(section_files)}


def print_scores(scores: dict, label: str) -> None:
    print(f"\n{'='*50}")
    print(f"EVALUATION — {label}")
    print(f"{'='*50}")
    dims = ["clarity", "conciseness", "technical", "sources", "tone", "slop"]
    for dim in dims:
        if dim in scores:
            s = scores[dim]
            score = s.get("score", "N/A")
            bar = "█" * int(score) + "░" * (10 - int(score)) if isinstance(score, (int, float)) else ""
            print(f"  {dim:<15} {score:>4} {bar}  {s.get('notes', '')}")
    if "overall" in scores:
        print(f"\n  {'OVERALL':<15} {scores['overall']:>4}")
    if "weakest_dimension" in scores:
        print(f"\n  Weakest: {scores['weakest_dimension']}")
    if scores.get("suggestions"):
        print(f"\n  Suggestions:")
        for sug in scores["suggestions"][:3]:
            print(f"    - {sug}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate article quality")
    parser.add_argument("--phase", choices=["foundation", "section", "full"])
    parser.add_argument("--section", type=int)
    parser.add_argument("--output", help="Write JSON to file")
    args = parser.parse_args()

    if args.phase == "foundation":
        result = score_foundation()
        print_scores(result, "FOUNDATION")
    elif args.phase == "section" or args.section:
        result = score_section(args.section or 1)
        print_scores(result, f"SECTION {args.section or 1}")
    elif args.phase == "full":
        result = score_full()
        print_scores(result["scores"], "FULL ARTICLE")
        print(f"\n  Files: {result['files_scanned']}")
        for f in result.get("slop_mechanical", []):
            print(f"    {f['file']}: tier1={f['tier1']}, weasel={f['weasel']}, passive={f['passive_ratio']:.0%}")
    else:
        # Auto
        if Path("sections").exists() and list(Path("sections").glob("section_*.md")):
            result = score_full()
            print_scores(result["scores"], "FULL (auto)")
        elif Path("outline.md").exists():
            result = score_foundation()
            print_scores(result, "FOUNDATION (auto)")
        else:
            print("Error: no article files found")
            sys.exit(1)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result if isinstance(result, dict) and "scores" in result else result, indent=2))
        print(f"\nScores written to: {args.output}")

    # Gate check
    phase = load_state().get("phase", "unknown")
    if phase == "foundation" and "overall" in (result if isinstance(result, dict) else {}):
        gate = 7.0
        status = "PASS" if result["overall"] >= gate else "BELOW GATE"
        print(f"  Foundation gate ({gate}): {status}")
    elif phase == "drafting":
        overall = result.get("scores", {}).get("overall") if isinstance(result, dict) else None
        if overall is not None:
            gate = 6.0
            status = "PASS" if overall >= gate else "BELOW GATE"
            print(f"  Draft gate ({gate}): {status}")


if __name__ == "__main__":
    main()

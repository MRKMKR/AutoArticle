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


def score_text(text: str, context: str, n_calls: int = 1) -> dict:
    """Score article text. When n_calls > 1, averages scores across multiple judge calls
    for stability. Particularly useful for per-section scoring where judge variance
    can swamp the signal."""
    if n_calls <= 1:
        prompt = f"""Evaluate this article.

## Article Text

{text[:8000]}

## Context

{context[:4000]}"""
        raw = api_post(prompt, system=SYSTEM, max_tokens=1024)
        return parse_json_response(raw)

    # n_calls > 1: collect all responses and average
    dims = ["clarity", "conciseness", "technical", "sources", "tone", "slop"]
    weights = [0.25, 0.15, 0.25, 0.20, 0.10, 0.05]

    all_scores: list[dict] = []
    for i in range(n_calls):
        call_context = f"{context[:4000]}\n\n[Evaluation round {i + 1} of {n_calls}]"
        prompt = f"""Evaluate this article.

## Article Text

{text[:8000]}

## Context

{call_context}"""
        raw = api_post(prompt, system=SYSTEM, max_tokens=1024)
        result = parse_json_response(raw)

        # Extract numeric scores — handle both dict format and bare int format
        scored = {}
        for d in dims:
            val = result.get(d, {})
            if isinstance(val, dict):
                s = val.get("score", 6)
            else:
                s = int(val) if val is not None else 6
            scored[d] = max(0, min(10, s))  # clamp to 0-10
        all_scores.append(scored)

    # Average each dimension across all calls
    averaged: dict = {}
    for d in dims:
        vals = [s[d] for s in all_scores if d in s]
        avg = round(sum(vals) / len(vals), 1) if vals else 6.0
        # Preserve notes from the first call only
        notes = ""
        averaged[d] = {"score": avg, "notes": notes}

    # Overall = weighted average of averaged dimensions
    total_w = sum(weights)
    overall = round(
        sum(averaged.get(d, {}).get("score", 6) * w for d, w in zip(dims, weights)) / total_w, 1
    )

    # Weakest = dimension with lowest averaged score
    weakest = min(dims, key=lambda d: averaged.get(d, {}).get("score", 10))

    # Suggestions from first call
    suggestions = all_scores[0].get("suggestions", []) if all_scores else []

    return {
        **{d: v for d, v in averaged.items()},
        "overall": overall,
        "weakest_dimension": weakest,
        "suggestions": suggestions,
        "_n_calls": n_calls,  # metadata for debugging
    }


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
    return score_text(text, context, n_calls=3)


def score_all_sections() -> dict:
    """Score every section individually. Returns per-section scores with the
    weakest section identified.

    Output format:
    {
        "per_section": [
            {"section": 1, "overall": 7.0, "weakest": "conciseness",
             "clarity": 8, "conciseness": 6, ...},
            ...
        ],
        "weakest_section": 3,        # section number with lowest overall
        "weakest_dimension": "conciseness",  # most common weakest across all
        "full_article_score": {...},  # existing full-article scores
    }
    """
    section_files = sorted(Path("sections").glob("section_*.md"))

    # Sort naturally by section number
    def section_num(f):
        import re
        m = re.search(r"section_(\d+)", f.name)
        return int(m.group(1)) if m else 0

    section_files.sort(key=section_num)

    per_section = []
    for sf in section_files:
        m = re.search(r"section_(\d+)", sf.name)
        if not m:
            continue
        s_num = int(m.group(1))
        scores = score_section(s_num)

        dims = ["clarity", "conciseness", "technical", "sources", "tone", "slop"]
        weights = [0.25, 0.15, 0.25, 0.20, 0.10, 0.05]
        total_w = sum(weights)

        def get_score(scores, d, default=6):
            val = scores.get(d, default)
            if isinstance(val, dict):
                return val.get("score", default)
            return max(0, min(10, int(val) if val is not None else default))

        overall = round(
            sum(get_score(scores, d) * w for d, w in zip(dims, weights)) / total_w, 1
        )

        # Find weakest dimension for this section
        weakest = min(dims, key=lambda d: get_score(scores, d, 10))

        entry = {"section": s_num, "overall": overall, "weakest": weakest}
        for d in dims:
            entry[d] = get_score(scores, d)

        per_section.append(entry)

    # Weakest section = lowest overall score
    weakest_entry = min(per_section, key=lambda x: x["overall"])
    weakest_section = weakest_entry["section"]

    # Most common weakest dimension across all sections
    weakest_counts = {}
    for e in per_section:
        w = e["weakest"]
        weakest_counts[w] = weakest_counts.get(w, 0) + 1
    weakest_dimension = max(weakest_counts, key=weakest_counts.get)

    # Global overall = mean of per-section overalls
    overall = round(sum(e["overall"] for e in per_section) / len(per_section), 1) if per_section else 0.0

    return {
        "per_section": per_section,
        "weakest_section": weakest_section,
        "weakest_dimension": weakest_dimension,
        "weakest_entry": weakest_entry,
        "overall": overall,
        "scores": {
            "overall": overall,
            "weakest_dimension": weakest_dimension,
        },  # backward-compat with existing pipeline code
    }


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

    scores = score_text(text, context, n_calls=3)
    dims = ["clarity", "conciseness", "technical", "sources", "tone", "slop"]
    weights = [0.25, 0.15, 0.25, 0.20, 0.10, 0.05]
    total_w = sum(weights)

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

    def get_score(scores, d, default=6):
        val = scores.get(d, default)
        if isinstance(val, dict):
            return val.get("score", default)
        return max(0, min(10, int(val) if val is not None else default))

    adj = max(0, get_score(scores, "slop", 7) - penalty)
    if isinstance(scores.get("slop"), dict):
        scores["slop"]["score"] = round(adj, 1)
        scores["slop"]["notes"] = scores["slop"].get("notes", "") + f" (mech: tier1={total_t1}, weasel={total_weasel}, passive={avg_passive:.0%})"
    else:
        scores["slop"] = {"score": round(adj, 1), "notes": f"mech: tier1={total_t1}, weasel={total_weasel}, passive={avg_passive:.0%}"}

    # Recompute overall
    scores["overall"] = round(
        sum(get_score(scores, d) * w for d, w in zip(dims, weights)) / total_w, 1
    )

    return {"scores": scores, "slop_mechanical": slop_mechanical, "files_scanned": len(section_files)}


def print_scores(scores: dict, label: str) -> None:
    print(f"\n{'='*50}")
    print(f"EVALUATION — {label}")
    print(f"{'='*50}")
    dims = ["clarity", "conciseness", "technical", "sources", "tone", "slop"]
    for dim in dims:
        if dim in scores:
            val = scores[dim]
            if isinstance(val, dict):
                score = val.get("score", "N/A")
                notes = val.get("notes", "")
            else:
                score = val
                notes = ""
            bar = "█" * int(score) + "░" * (10 - int(score)) if isinstance(score, (int, float)) else ""
            print(f"  {dim:<15} {score:>4} {bar}  {notes}")
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
    parser.add_argument("--phase", choices=["foundation", "section", "full", "per-section"])
    parser.add_argument("--section", type=int)
    parser.add_argument("--output", help="Write JSON to file")
    args = parser.parse_args()

    if args.phase == "foundation":
        result = score_foundation()
        print_scores(result, "FOUNDATION")
    elif args.phase == "section" or args.section:
        result = score_section(args.section or 1)
        print_scores(result, f"SECTION {args.section or 1}")
    elif args.phase == "per-section":
        result = score_all_sections()
        print(f"\n{'='*50}")
        print(f"PER-SECTION SCORES")
        print(f"{'='*50}")
        for entry in result["per_section"]:
            bar = "█" * int(entry["overall"]) + "░" * (10 - int(entry["overall"]))
            print(f"  Section {entry['section']:>2}: {entry['overall']:>4}  {bar}  weakest={entry['weakest']}")
        print(f"\n  → Target section {result['weakest_section']} (lowest score)")
        print(f"  → Weakest dimension overall: {result['weakest_dimension']}")
        print(f"  → Per-section weakest: {result['weakest_entry']}")
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
        # score_all_sections returns top-level keys, score_full returns {"scores": ..., "slop_mechanical": ...}
        out_data = result if isinstance(result, dict) and "scores" in result else result
        out_path.write_text(json.dumps(out_data, indent=2))
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

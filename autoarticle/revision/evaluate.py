#!/usr/bin/env python3
"""
Evaluate article quality across 6 dimensions.

Usage:
    python evaluate.py --phase=foundation [--outline outline.md] [--voice voice.md]
    python evaluate.py --section=N [--text sections/section_NN.md]
    python evaluate.py --full [--sections sections/]
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from autoarticle.utils.config import load_config
from autoarticle.utils.state import load_state

import httpx


# Evaluation prompt for the judge model
SYSTEM_PROMPT = """You are an expert article evaluator. Score articles on 6 dimensions. Be strict but fair. Rate 0-10 per dimension. Output ONLY valid JSON.

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
}
"""


DIMENSION_WEIGHTS = {
    "clarity": 0.25,
    "conciseness": 0.15,
    "technical": 0.25,
    "sources": 0.20,
    "tone": 0.10,
    "slop": 0.05,
}


def call_judge(text: str, context: str, config) -> dict:
    """Call judge model for evaluation."""
    prompt = f"""Evaluate this article.

## Article Text

{text[:8000]}

## Context

{context[:4000]}
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
            "max_tokens": 1024,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        },
    )

    if response.status_code != 200:
        raise RuntimeError(f"API error: {response.status_code} {response.text}")

    raw = response.json()["content"][0]["text"]

    # Strip markdown code blocks
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"```\s*$", "", raw)
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Warning: JSON parse failed: {e}")
        print(f"Raw: {raw[:200]}")
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


def score_file(path: Path, context: str, config) -> dict:
    """Score a single file."""
    text = path.read_text()
    return call_judge(text, context, config)


def score_foundation(outline_path: Path, config) -> dict:
    """Score foundation documents."""
    parts = []
    for fname in ["outline.md", "voice.md", "sources.md"]:
        p = Path(fname)
        if p.exists():
            parts.append(f"=== {fname} ===\n{p.read_text()[:3000]}")

    text = "\n\n".join(parts)
    context = "Foundation phase: scoring outline structure, voice guide, and source identification."
    return call_judge(text, context, config)


def score_section(section_num: int, config) -> dict:
    """Score a single section."""
    section_path = Path(f"sections/section_{section_num:02d}.md")
    if not section_path.exists():
        print(f"Error: section not found: {section_path}")
        sys.exit(1)

    # Build context
    ctx_parts = []
    for fname in ["seed.txt", "outline.md", "voice.md"]:
        p = Path(fname)
        if p.exists():
            ctx_parts.append(f"=== {fname} ===\n{p.read_text()[:2000]}")

    # Add previous and next sections for continuity
    prev = Path(f"sections/section_{section_num-1:02d}.md")
    next_s = Path(f"sections/section_{section_num+1:02d}.md")
    if prev.exists():
        ctx_parts.append(f"=== previous section ===\n{prev.read_text()[:500]}")
    if next_s.exists():
        ctx_parts.append(f"=== next section ===\n{next_s.read_text()[:500]}")

    context = "\n\n".join(ctx_parts)
    return score_file(section_path, context, config)


def score_full(config) -> dict:
    """Score the complete article."""
    sections_dir = Path("sections")

    # Read all sections in order
    section_files = sorted(sections_dir.glob("section_*.md"))
    all_text = []
    for sf in section_files:
        content = sf.read_text()
        all_text.append(f"=== {sf.name} ===\n{content}")

    text = "\n\n".join(all_text)

    # Context: planning docs
    ctx_parts = []
    for fname in ["seed.txt", "outline.md", "voice.md", "sources.md"]:
        p = Path(fname)
        if p.exists():
            ctx_parts.append(f"=== {fname} ===\n{p.read_text()[:2000]}")
    context = "\n\n".join(ctx_parts)

    # Also run anti_slop mechanically
    from autoarticle.drafting.anti_slop import scan_file

    slop_findings = []
    for sf in section_files:
        findings = scan_file(sf)
        slop_findings.append({
            "file": sf.name,
            "tier1": len(findings["tier1"]),
            "tier2": len(findings["tier2"]),
            "inflation": len(findings["inflation"]),
            "weasel": len(findings["weasel"]),
            "passive_ratio": findings["passive_ratio"],
        })

    llm_scores = call_judge(text, context, config)

    # Adjust slop dimension based on mechanical scan
    total_t1 = sum(f["tier1"] for f in slop_findings)
    total_weasel = sum(f["weasel"] for f in slop_findings)
    avg_passive = sum(f["passive_ratio"] for f in slop_findings) / max(len(slop_findings), 1)

    mechanical_slop_penalty = 0
    if total_t1 > 0:
        mechanical_slop_penalty += total_t1 * 0.5
    if total_weasel > 2:
        mechanical_slop_penalty += (total_weasel - 2) * 0.2
    if avg_passive > 0.15:
        mechanical_slop_penalty += 1.0

    adjusted_slop = max(0, llm_scores.get("slop", {}).get("score", 7) - mechanical_slop_penalty)
    llm_scores["slop"]["score"] = round(adjusted_slop, 1)
    llm_scores["slop"]["notes"] += f" (mechanical: {total_t1} tier1, {total_weasel} weasel, {avg_passive:.0%} passive)"

    # Recompute overall
    dimensions = ["clarity", "conciseness", "technical", "sources", "tone", "slop"]
    total_weight = sum(DIMENSION_WEIGHTS[d] for d in dimensions)
    overall = sum(
        llm_scores.get(d, {}).get("score", 6) * DIMENSION_WEIGHTS[d]
        for d in dimensions
    ) / total_weight
    llm_scores["overall"] = round(overall, 1)

    return {
        "scores": llm_scores,
        "slop_mechanical": slop_findings,
        "files_scanned": len(section_files),
    }


def print_scores(scores: dict, phase: str = "unknown") -> None:
    """Print scores in a readable format."""
    print(f"\n{'='*50}")
    print(f"EVALUATION — {phase}")
    print(f"{'='*50}")

    dimensions = ["clarity", "conciseness", "technical", "sources", "tone", "slop"]
    for dim in dimensions:
        if dim in scores:
            s = scores[dim]
            score = s.get("score", "N/A")
            notes = s.get("notes", "")
            bar = "█" * int(score) + "░" * (10 - int(score)) if isinstance(score, (int, float)) else ""
            print(f"  {dim:<15} {score:>4} {bar}  {notes}")

    if "overall" in scores:
        print(f"\n  {'OVERALL':<15} {scores['overall']:>4}")

    if "weakest_dimension" in scores:
        print(f"\n  Weakest: {scores['weakest_dimension']}")

    if "suggestions" in scores and scores["suggestions"]:
        print(f"\n  Suggestions:")
        for suggestion in scores["suggestions"][:3]:
            print(f"    - {suggestion}")

    print()


def main():
    parser = argparse.ArgumentParser(description="Evaluate article quality")
    parser.add_argument("--phase", choices=["foundation", "section", "full"], help="Evaluation mode")
    parser.add_argument("--section", type=int, help="Section number to evaluate")
    parser.add_argument("--outline", default="outline.md")
    parser.add_argument("--voice", default="voice.md")
    parser.add_argument("--output", help="Write JSON output to file")
    args = parser.parse_args()

    config = load_config()

    if args.phase == "foundation":
        scores = score_foundation(Path(args.outline), config)
        print_scores(scores, "FOUNDATION")

    elif args.phase == "section" or args.section:
        section_num = args.section or 1
        scores = score_section(section_num, config)
        print_scores(scores, f"SECTION {section_num}")

    elif args.phase == "full":
        result = score_full(config)
        scores = result["scores"]
        print_scores(scores, "FULL ARTICLE")
        print(f"  Files scanned: {result['files_scanned']}")
        slop = result.get("slop_mechanical", [])
        if slop:
            print(f"\n  Slop breakdown by section:")
            for f in slop:
                print(f"    {f['file']}: tier1={f['tier1']}, weasel={f['weasel']}, passive={f['passive_ratio']:.0%}")

    else:
        # Auto-detect
        if Path("sections").exists() and list(Path("sections").glob("section_*.md")):
            result = score_full(config)
            scores = result["scores"]
            print_scores(scores, "FULL ARTICLE (auto)")
        elif Path("outline.md").exists():
            scores = score_foundation(Path(args.outline), config)
            print_scores(scores, "FOUNDATION (auto)")
        else:
            print("Error: no article files found")
            sys.exit(1)

    if args.output:
        Path(args.output).write_text(json.dumps(scores, indent=2))
        print(f"\nScores written to: {args.output}")

    # Check gates
    phase = load_state().get("phase", "unknown")
    if phase == "foundation" and "overall" in scores:
        gate = 7.0
        status = "PASS" if scores["overall"] >= gate else "BELOW GATE"
        print(f"  Foundation gate ({gate}): {status}")
    elif phase == "drafting" and "overall" in scores:
        gate = 6.0
        status = "PASS" if scores["overall"] >= gate else "BELOW GATE"
        print(f"  Draft gate ({gate}): {status}")


if __name__ == "__main__":
    main()

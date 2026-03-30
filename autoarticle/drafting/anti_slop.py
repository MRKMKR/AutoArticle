#!/usr/bin/env python3
"""
Anti-slop enforcement: scan and rewrite sections for AI writing tells.

Usage:
    python anti_slop.py <file_or_dir> [--mode scan|rewrite|full-rewrite]
"""
import argparse
import re
import sys
from pathlib import Path


# Tier 1: Kill on sight
TIER1 = [
    r"\bdelve\b",
    r"\butilize\b",
    r"\bleverage\b(?=\s+(?:as\s+a|this|that|those|the\s+\w+))",  # verb usage
    r"\bfacilitate\b",
    r"\belucidate\b",
    r"\bembark\b",
    r"\bendeavor\b",
    r"\bencompass\b",
    r"\bmultifaceted\b",
    r"\btapestry\b",
    r"\btestament\b",
    r"\bparadigm\b",
    r"\bsynergy\b",
    r"\bholistic\b",
    r"\bcatalyze\b",
    r"\bjuxtapose\b",
    r"\brealm\b",
    r"\blandscape\b(?=\s+(?:of|for|in))",  # metaphorical
    r"\bmyriad\b",
    r"\bplethora\b",
]

# Tier 2: Suspicious in clusters
TIER2 = [
    r"\brobust\b",
    r"\bcomprehensive\b",
    r"\bseamless(?:ly)?\b",
    r"\bcutting-edge\b",
    r"\binnovative\b",
    r"\bstreamline\b",
    r"\bempower\b",
    r"\bfoster\b",
    r"\benhance\b",
    r"\belevate\b",
    r"\boptimize\b",
    r"\bscalable\b",
    r"\bpivotal\b",
    r"\bintricate\b",
    r"\bprofound\b",
    r"\bresonate\b",
    r"\bunderscore\b",
    r"\bharness\b",
    r"\bnavigate\b(?=\s+(?:the\s+)?(?:complex|challenging|difficult))",
    r"\bcultivate\b",
    r"\bbolster\b",
    r"\bgalvanize\b",
    r"\bcornerstone\b",
    r"\bgame-changer\b",
    r"\btransformative\b",
]

# Tier 3: Filler phrases
TIER3 = [
    (r"It's worth noting that[,.\s]", ""),
    (r"It's important to note that[,.\s]", ""),
    (r"In conclusion[,.\s]", ""),
    (r"To summarize[,.\s]", ""),
    (r"The fact of the matter is that\s+", ""),
    (r"It goes without saying that\s+", ""),
    (r"Needless to say[,.\s]", ""),
    (r"As previously stated[,.\s]", ""),
    (r"At the end of the day[,.\s]", ""),
]

# Claim inflation
INFLATION = [
    r"\brevolutionary\b",
    r"\bgroundbreaking\b",
    r"\bdisruptive\b",
    r"\bgame-changing\b",
]

# Weasel words
WEASEL = [
    r"\bit is believed that\b",
    r"\bexperts say\b",
    r"\bresearch suggests that\b",
    r"\bit is thought that\b",
    r"\bstudies show that\b",
    r"\bevidence points to\b",
]

# Vague quantification
VAGUE_QUANT = [
    r"\bmany\b(?!\s+(?:of\s+)?(?:us|you|people|developers))",
    r"\bseveral\b",
    r"\bsignificantly\b",
    r"\bquite\b",
    r"\brather\b",
    r"\ba lot\b",
]


def scan_file(path: Path) -> dict:
    """Scan a single file for slop patterns. Returns report dict."""
    text = path.read_text()
    findings = {
        "path": str(path),
        "tier1": [],
        "tier2": [],
        "tier3": [],
        "inflation": [],
        "weasel": [],
        "vague": [],
        "passive_count": 0,
        "total_sentences": 0,
        "passive_ratio": 0.0,
    }

    # Tier 1
    for pattern in TIER1:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            line_num = text[: match.start()].count("\n") + 1
            findings["tier1"].append({"pattern": pattern, "line": line_num, "text": match.group()})

    # Tier 2
    for pattern in TIER2:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            line_num = text[: match.start()].count("\n") + 1
            findings["tier2"].append({"pattern": pattern, "line": line_num, "text": match.group()})

    # Tier 3
    for pattern, replacement in TIER3:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if matches:
            line_num = text[: matches[0].start()].count("\n") + 1
            findings["tier3"].append({"pattern": pattern, "line": line_num, "count": len(matches)})

    # Inflation
    for pattern in INFLATION:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            line_num = text[: match.start()].count("\n") + 1
            findings["inflation"].append({"pattern": pattern, "line": line_num, "text": match.group()})

    # Weasel
    for pattern in WEASEL:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            line_num = text[: match.start()].count("\n") + 1
            findings["weasel"].append({"pattern": pattern, "line": line_num, "text": match.group()})

    # Vague
    for pattern in VAGUE_QUANT:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            line_num = text[: match.start()].count("\n") + 1
            findings["vague"].append({"pattern": pattern, "line": line_num, "text": match.group()})

    # Passive voice detection
    passive_pattern = re.compile(r"\b(is|are|was|were|been|being)\s+\w+ed\b", re.IGNORECASE)
    sentences = re.split(r"[.!?]+", text)
    findings["total_sentences"] = len(sentences)
    findings["passive_count"] = len(passive_pattern.findall(text))
    if sentences:
        findings["passive_ratio"] = findings["passive_count"] / max(findings["total_sentences"], 1)

    return findings


def print_report(findings: dict) -> None:
    """Print a human-readable report."""
    path = findings["path"]
    print(f"\n{'='*60}")
    print(f"FILE: {path}")
    print(f"{'='*60}")

    if not any(
        [
            findings["tier1"],
            findings["tier2"],
            findings["tier3"],
            findings["inflation"],
            findings["weasel"],
            findings["vague"],
        ]
    ):
        print("  No slop patterns detected.")
        return

    if findings["tier1"]:
        print(f"\n  TIER 1 (kill on sight): {len(findings['tier1'])} instances")
        for f in findings["tier1"]:
            print(f"    L{f['line']}: [{f['text']}]")

    if findings["tier2"]:
        count_by_line: dict = {}
        for f in findings["tier2"]:
            count_by_line[f["line"]] = count_by_line.get(f["line"], 0) + 1
        print(f"\n  TIER 2 (clusters = problem): {len(findings['tier2'])} instances")
        for line, count in sorted(count_by_line.items()):
            print(f"    L{line}: {count} occurrence(s)")

    if findings["tier3"]:
        print(f"\n  TIER 3 (filler phrases):")
        for f in findings["tier3"]:
            print(f"    L{f['line']}: pattern '{f['pattern'].strip()}' x{f['count']}")

    if findings["inflation"]:
        print(f"\n  CLAIM INFLATION:")
        for f in findings["inflation"]:
            print(f"    L{f['line']}: [{f['text']}]")

    if findings["weasel"]:
        print(f"\n  WEASEL WORDS:")
        for f in findings["weasel"]:
            print(f"    L{f['line']}: [{f['text']}]")

    if findings["vague"]:
        print(f"\n  VAGUE QUANTIFICATION:")
        for f in findings["vague"]:
            print(f"    L{f['line']}: [{f['text']}]")

    passive_pct = findings["passive_ratio"] * 100
    print(f"\n  Passive voice: {findings['passive_count']}/{findings['total_sentences']} sentences ({passive_pct:.0f}%)")
    if passive_pct > 15:
        print(f"    WARNING: >15% passive — review flagged")


def rewrite_text(text: str) -> str:
    """Apply Tier 3 filler phrase removals to text."""
    result = text
    for pattern, replacement in TIER3:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def rewrite_with_llm(path: Path, config) -> str:
    """Use LLM to rewrite flagged passages."""
    import httpx

    findings = scan_file(path)
    if not any([findings["tier1"], findings["tier2"], findings["inflation"], findings["weasel"], findings["vague"]]):
        return path.read_text()  # No changes needed

    prompt = f"""Rewrite this text to remove AI slop patterns while preserving meaning.

Remove or replace:
- Tier 1 words: delve, utilize, leverage (verb), facilitate, elucidate, embark, 
  endeavor, encompass, multifaceted, tapestry, testament, paradigm, synergy, 
  holistic, catalyze, juxtapose, realm, landscape (metaphorical), myriad, plethora
- Claim inflation: revolutionary, groundbreaking, game-changing, disruptive
- Weasel words: "experts say", "research suggests", "it is believed that", etc.
- Vague quantification without specifics

Rewrite flagged sentences to be direct and human. Do not change facts or add new content.

Original text:
{path.read_text()}
"""

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
            "max_tokens": 2048,
            "system": "You are an expert editor. Remove AI slop from text.",
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    if response.status_code != 200:
        raise RuntimeError(f"API error: {response.status_code} {response.text}")
    return response.json()["content"][0]["text"]


def main():
    parser = argparse.ArgumentParser(description="Anti-slop scanner and rewriter")
    parser.add_argument("target", help="File or directory to scan")
    parser.add_argument("--mode", choices=["scan", "rewrite", "full-rewrite"], default="scan")
    parser.add_argument("--output", help="Output file (for rewrite modes)")
    args = parser.parse_args()

    target = Path(args.target)
    mode = args.mode

    from autoarticle.utils.config import load_config

    if mode in ("rewrite", "full-rewrite"):
        config = load_config()

    files = []
    if target.is_dir():
        files = sorted(target.glob("*.md"))
    elif target.is_file():
        files = [target]
    else:
        print(f"Error: not found: {target}")
        sys.exit(1)

    if not files:
        print(f"No .md files found in: {target}")
        sys.exit(0)

    all_findings = []
    for f in files:
        findings = scan_file(f)
        all_findings.append(findings)
        print_report(findings)

        if mode in ("rewrite", "full-rewrite") and findings["tier1"]:
            print(f"\n  Rewriting {f}...")
            new_text = rewrite_with_llm(f, config)
            output_path = Path(args.output) if args.output else f
            output_path.write_text(new_text)
            print(f"  Written to: {output_path}")

    # Summary
    total_t1 = sum(len(f["tier1"]) for f in all_findings)
    total_t2 = sum(len(f["tier2"]) for f in all_findings)
    total_inflation = sum(len(f["inflation"]) for f in all_findings)
    total_weasel = sum(len(f["weasel"]) for f in all_findings)

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"  Files scanned: {len(files)}")
    print(f"  Tier 1 (kill): {total_t1}")
    print(f"  Tier 2 (cluster): {total_t2}")
    print(f"  Claim inflation: {total_inflation}")
    print(f"  Weasel words: {total_weasel}")

    if total_t1 > 0:
        print(f"\n  -> REWRITE recommended (Tier 1 instances found)")
    elif total_t2 > 3:
        print(f"\n  -> REVIEW recommended (Tier 2 clusters)")


if __name__ == "__main__":
    main()

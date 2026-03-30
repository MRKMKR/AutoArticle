#!/usr/bin/env python3
"""
Anti-slop enforcement: scan and rewrite sections for AI writing tells.

Usage:
    python anti_slop.py <file_or_dir> [--mode scan|rewrite]
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from autoarticle.utils.api import api_post


# Tier 1: Kill on sight
TIER1 = [
    r"\bdelve\b",
    r"\butilize\b",
    r"\bleverage\b(?=\s+(?:as\s+a|this|that|those|the\s+\w+))",
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
    r"\blandscape\b(?=\s+(?:of|for|in))",
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
    (r"It's worth noting that\b[,.\s]", ""),
    (r"It's important to note that\b[,.\s]", ""),
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
    """Scan a single file for slop patterns."""
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

    for pattern in TIER1:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            findings["tier1"].append({
                "pattern": pattern,
                "line": text[:match.start()].count("\n") + 1,
                "text": match.group(),
            })

    for pattern in TIER2:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            findings["tier2"].append({
                "pattern": pattern,
                "line": text[:match.start()].count("\n") + 1,
                "text": match.group(),
            })

    for pattern, replacement in TIER3:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if matches:
            findings["tier3"].append({
                "pattern": pattern,
                "line": text[:matches[0].start()].count("\n") + 1,
                "count": len(matches),
            })

    for pattern in INFLATION:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            findings["inflation"].append({
                "pattern": pattern,
                "line": text[:match.start()].count("\n") + 1,
                "text": match.group(),
            })

    for pattern in WEASEL:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            findings["weasel"].append({
                "pattern": pattern,
                "line": text[:match.start()].count("\n") + 1,
                "text": match.group(),
            })

    for pattern in VAGUE_QUANT:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            findings["vague"].append({
                "pattern": pattern,
                "line": text[:match.start()].count("\n") + 1,
                "text": match.group(),
            })

    passive_pattern = re.compile(r"\b(is|are|was|were|been|being)\s+\w+ed\b", re.IGNORECASE)
    sentences = re.split(r"[.!?]+", text)
    findings["total_sentences"] = max(len(sentences), 1)
    findings["passive_count"] = len(passive_pattern.findall(text))
    findings["passive_ratio"] = findings["passive_count"] / findings["total_sentences"]

    return findings


def print_report(findings: dict) -> None:
    """Print a human-readable report."""
    path = findings["path"]
    print(f"\n{'='*50}")
    print(f"FILE: {path}")
    print(f"{'='*50}")

    if not any([findings["tier1"], findings["tier2"], findings["tier3"],
                findings["inflation"], findings["weasel"], findings["vague"]]):
        print("  No slop patterns detected.")
        return

    if findings["tier1"]:
        print(f"\n  TIER 1 (kill on sight): {len(findings['tier1'])} instances")
        for f in findings["tier1"]:
            print(f"    L{f['line']}: [{f['text']}]")

    if findings["tier2"]:
        by_line = {}
        for f in findings["tier2"]:
            by_line.setdefault(f["line"], []).append(f)
        print(f"\n  TIER 2 (clusters = problem): {len(findings['tier2'])} instances")
        for line, items in sorted(by_line.items()):
            print(f"    L{line}: {len(items)} occurrence(s)")

    if findings["tier3"]:
        print(f"\n  TIER 3 (filler phrases):")
        for f in findings["tier3"]:
            print(f"    L{f['line']}: pattern x{f['count']}")

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

    pct = findings["passive_ratio"] * 100
    print(f"\n  Passive voice: {findings['passive_count']}/{findings['total_sentences']} ({pct:.0f}%)")
    if pct > 15:
        print(f"    WARNING: >15% passive — review flagged")


SYSTEM_REWRITE = """You are an expert editor. Remove AI slop from text while preserving all facts and meaning.

Remove or replace:
- Tier 1 words: delve, utilize, leverage (verb), facilitate, elucidate, embark,
  endeavor, encompass, multifaceted, tapestry, testament, paradigm, synergy,
  holistic, catalyze, juxtapose, realm, landscape (metaphorical), myriad, plethora
- Claim inflation: revolutionary, groundbreaking, game-changing, disruptive
- Weasel words: "experts say", "research suggests", "it is believed that", etc.
- Vague quantification without specifics

Rewrite flagged sentences to be direct and human. Do not change facts or add new content.
Output ONLY the rewritten text."""


def rewrite_with_llm(path: Path) -> str:
    """Use LLM to rewrite text with slop removed."""
    text = path.read_text()
    return api_post(text, system=SYSTEM_REWRITE, max_tokens=2048)


def rewrite_text(text: str) -> str:
    """Apply Tier 3 filler phrase removals to text (no API call)."""
    result = text
    for pattern, replacement in TIER3:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def main():
    parser = argparse.ArgumentParser(description="Anti-slop scanner and rewriter")
    parser.add_argument("target", help="File or directory to scan")
    parser.add_argument("--mode", choices=["scan", "rewrite"], default="scan")
    parser.add_argument("--output", help="Output file (for rewrite mode)")
    args = parser.parse_args()

    target = Path(args.target)
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

        if args.mode == "rewrite" and findings["tier1"]:
            print(f"\n  Rewriting {f}...")
            new_text = rewrite_with_llm(f)
            output_path = Path(args.output) if args.output else f
            output_path.write_text(new_text)
            print(f"  Written to: {output_path}")

    total_t1 = sum(len(f["tier1"]) for f in all_findings)
    total_t2 = sum(len(f["tier2"]) for f in all_findings)

    print(f"\n{'='*50}")
    print("SUMMARY")
    print(f"{'='*50}")
    print(f"  Files scanned: {len(files)}")
    print(f"  Tier 1 (kill): {total_t1}")
    print(f"  Tier 2 (cluster): {total_t2}")
    if total_t1 > 0:
        print(f"\n  -> REWRITE recommended")


if __name__ == "__main__":
    main()

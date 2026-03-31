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

# Structural: formulaic section openers
SECTION_OPENERS = [
    r"\bImagine\b",
    r"\bPicture\b",
    r"\bConsider\b",
    r"\bVisualize\b",
    r"\bThink of\b",
    r"\bLet's imagine\b",
    r"\bWhat if I told you\b",
]

# Structural: anaphoric sentence openers (same word starts multiple sentences close together)
ANAPHORA_STARTERS = [
    "this", "such", "these", "it", "that",
]

# Structural: explanatory closing formulas
EXPLANATORY_CLOSE = [
    r"what this (means|shows|suggests|indicates)",
    r"in other words",
    r"to put it another way",
    r"to sum up",
    r"the key takeaway is",
    r"the bottom line is",
    r"here's the thing",
    r"the point is",
]

# Structural: filler sentence starters (especially AI)
FILLER_STARTERS = [
    r"\bImportantly\b",
    r"\bAdditionally\b",
    r"\bFurthermore\b",
    r"\bMoreover\b",
    r"\bIn fact\b",
    r"\bAs a result\b",
    r"\bThis (means|implies|suggests|indicates|shows|reveals)\b",
]

# Structural: rhetorical questions
RHETORICAL_Q = [
    r"\?$",
]


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    import unicodedata
    # Normalize unicode quotes
    text = unicodedata.normalize("NFKC", text)
    # Split on sentence boundaries
    raw = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in raw if s.strip()]


def _first_word(sentence: str) -> str:
    """Get the normalized first word of a sentence."""
    m = re.search(r"^([\"']?)([A-Za-z]+)", sentence)
    return m.group(2).lower() if m else ""


def _opening_phrase(sentence: str, max_words: int = 3) -> str:
    """Get the first N words of a sentence as a phrase."""
    words = re.findall(r"[A-Za-z]+", sentence)
    return " ".join(words[:max_words]).lower()


def scan_structural(text: str) -> dict:
    """Detect structural AI/LLM writing patterns."""
    findings = {
        "section_openers": [],
        "anaphora": [],
        "explanatory_close": [],
        "filler_starts": [],
        "rhetorical_questions": [],
        "paragraph_length_std": 0.0,
        "sentence_length_std": 0.0,
        "same_opener_count": 0,
        "structure_warnings": [],
    }

    import statistics

    sentences = _split_sentences(text)
    if len(sentences) < 3:
        return findings

    # --- Paragraph structure ---
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if paragraphs:
        para_lens = [len(p.split()) for p in paragraphs]
        if len(para_lens) > 1:
            findings["paragraph_length_std"] = round(statistics.stdev(para_lens), 2) if len(para_lens) > 1 else 0.0
            # Very low stddev = suspiciously uniform paragraphs
            mean_para = statistics.mean(para_lens)
            if mean_para > 0 and findings["paragraph_length_std"] < mean_para * 0.15:
                findings["structure_warnings"].append(
                    f"Uniform paragraph length (std={findings['paragraph_length_std']}, mean={mean_para:.0f} words) — AI often writes paragraphs of near-identical length"
                )

    # --- Sentence length variance ---
    sent_lens = [len(s.split()) for s in sentences]
    if len(sent_lens) > 2:
        findings["sentence_length_std"] = round(statistics.stdev(sent_lens), 2)
        mean_len = statistics.mean(sent_lens)
        if mean_len > 0 and findings["sentence_length_std"] < mean_len * 0.12:
            findings["structure_warnings"].append(
                f"Uniform sentence length (std={findings['sentence_length_std']}, mean={mean_len:.0f} words) — AI often produces sentences of near-identical length"
            )

    # --- Sentence first-word distribution ---
    first_words = [_first_word(s) for s in sentences]
    word_counts: dict[str, int] = {}
    for w in first_words:
        word_counts[w] = word_counts.get(w, 0) + 1

    # Flag if same opener starts 25%+ of sentences
    total_sents = len(sentences)
    for word, count in word_counts.items():
        if word in ANAPHORA_STARTERS and count >= max(3, int(total_sents * 0.25)):
            findings["anaphora"].append({
                "word": word,
                "count": count,
                "total_sentences": total_sents,
                "pct": round(count / total_sents * 100),
            })
            findings["same_opener_count"] += count

    # --- Section opener patterns (Imagine, Consider, Picture...) ---
    opener_counts: dict[str, int] = {}
    for si, sent in enumerate(sentences):
        for pattern in SECTION_OPENERS:
            if re.search(pattern, sent, re.IGNORECASE):
                phrase = _opening_phrase(sent, max_words=2)
                opener_counts[phrase] = opener_counts.get(phrase, 0) + 1
    for phrase, count in opener_counts.items():
        if count >= 2:
            findings["section_openers"].append({"phrase": phrase, "count": count})

    # --- Explanatory closing formulas ---
    for si, sent in enumerate(sentences):
        for pattern in EXPLANATORY_CLOSE:
            if re.search(pattern, sent, re.IGNORECASE):
                findings["explanatory_close"].append({
                    "phrase": pattern,
                    "line": text[:text.find(sentences[si])].count("\n") + 1,
                    "text": sent.strip()[:80],
                })

    # --- Filler sentence starters ---
    for si, sent in enumerate(sentences):
        for pattern in FILLER_STARTERS:
            if re.match(pattern, sent, re.IGNORECASE):
                findings["filler_starts"].append({
                    "pattern": pattern,
                    "line": text[:text.find(sentences[si])].count("\n") + 1,
                    "text": sent.strip()[:60],
                })

    # --- Rhetorical questions ---
    for si, sent in enumerate(sentences):
        # Ends with ? or is a question embedded
        if "?" in sent or re.match(r"^(why|how|what|when|where|who|can|could|would|does|is)\s+", sent, re.I):
            # Only flag if followed immediately by a statement (AI pattern)
            if si + 1 < len(sentences) and len(sent.split()) < 15:
                findings["rhetorical_questions"].append({
                    "line": text[:text.find(sentences[si])].count("\n") + 1,
                    "text": sent.strip()[:80],
                })

    return findings


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
        # Structural findings
        "section_openers": [],
        "anaphora": [],
        "explanatory_close": [],
        "filler_starts": [],
        "rhetorical_questions": [],
        "paragraph_length_std": 0.0,
        "sentence_length_std": 0.0,
        "same_opener_count": 0,
        "structure_warnings": [],
    }

    # Run structural detection
    structural = scan_structural(text)
    for key in ["section_openers", "anaphora", "explanatory_close", "filler_starts",
                "rhetorical_questions", "paragraph_length_std", "sentence_length_std",
                "same_opener_count", "structure_warnings"]:
        findings[key] = structural[key]

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

    # Structural findings
    if findings["structure_warnings"]:
        for w in findings["structure_warnings"]:
            print(f"\n  STRUCTURE: {w}")

    if findings["section_openers"]:
        print(f"\n  FORMULAIC OPENERS (Imagine/Consider/Picture...):")
        for o in findings["section_openers"]:
            print(f"    '{o['phrase']}' x{o['count']} — AI feels compelled to frame everything as a scene")

    if findings["anaphora"]:
        print(f"\n  ANAPHORA (This/Such/These overused as sentence starters):")
        for a in findings["anaphora"]:
            print(f"    '{a['word']}' starts {a['count']}/{a['total_sentences']} sentences ({a['pct']}%) — AI leans heavily on these")

    if findings["explanatory_close"]:
        print(f"\n  EXPLANATORY CLOSE formulas:")
        for e in findings["explanatory_close"]:
            print(f"    L{e['line']}: '{e['text'][:60]}...'")

    if findings["filler_starts"]:
        print(f"\n  FILLER SENTENCE STARTERS:")
        for f in findings["filler_starts"][:5]:
            print(f"    L{f['line']}: '{f['text'][:50]}...'")

    if findings["rhetorical_questions"]:
        print(f"\n  RHETORICAL QUESTIONS (question + immediate answer):")
        for r in findings["rhetorical_questions"][:3]:
            print(f"    L{r['line']}: '{r['text']}'")

    if findings["paragraph_length_std"] > 0:
        print(f"\n  Paragraph length std: {findings['paragraph_length_std']:.0f} words | Sentence length std: {findings['sentence_length_std']:.0f} words")


SYSTEM_REWRITE = """You are an expert editor. Remove AI slop from text while preserving all facts and meaning.

Remove or replace:
- Tier 1 words: delve, utilize, leverage (verb), facilitate, elucidate, embark,
  endeavor, encompass, multifaceted, tapestry, testament, paradigm, synergy,
  holistic, catalyze, juxtapose, realm, landscape (metaphorical), myriad, plethora
- Claim inflation: revolutionary, groundbreaking, game-changing, disruptive
- Weasel words: "experts say", "research suggests", "it is believed that", etc.
- Vague quantification without specifics
- Formulaic openers: "Imagine...", "Picture...", "Consider...", "Visualize...",
  "Think of...", "Let's imagine..."
- Excessive "This/Such/These/It" as sentence openers (anaphora)
- Explanatory close formulas: "What this means is...", "In other words...",
  "To sum up...", "Here's the thing...", "The point is..."
- Filler sentence starters: "Importantly...", "Additionally...",
  "Furthermore...", "Moreover...", "In fact...", "As a result...",
  "This means/suggests/implies..."
- Rhetorical question + immediate answer pairs
- Uniform paragraph and sentence length (vary it)

Rewrite flagged passages to be direct and human. Do not change facts or add new content.
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

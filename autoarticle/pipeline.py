#!/usr/bin/env python3
"""
Prerequisite checker for AutoArticle pipeline.

Validates that required files exist and contain meaningful content
before running each phase. Can be run standalone or imported.

Usage:
    python pipeline.py check [--phase foundation|draft|revision|polish]
    python pipeline.py check --all
"""
import argparse
import sys
from pathlib import Path


# Files required per phase
PHASE_REQUIREMENTS = {
    "foundation": {
        "seed.txt": (
            "Seed file with article spec",
            ["type:", "title:", "target_length:", "seed_bullets:"],
        ),
    },
    "draft": {
        "outline.md": (
            "Structured outline from gen_outline",
            ["Key Claims", "Target Length"],
        ),
        "voice.md": (
            "Voice guide from gen_voice",
            ["Tone", "Audience"],
        ),
        "sources.md": (
            "Source tracking from gen_sources",
            ["Sources", "Claim"],
        ),
        "claims.json": (
            "Structured claims from gen_claims (may be empty for opinion pieces)",
            ["["],  # Valid JSON array (empty or non-empty)
        ),
    },
    "revision": {
        "outline.md": None,  # inherited from draft
        "sections": (
            "Drafted sections directory",
            None,  # check is directory existence
        ),
    },
    "polish": {
        "outline.md": None,
        "sections": None,
    },
}

# Files needed to START a phase (inputs)
PHASE_INPUTS = {
    "foundation": ["seed.txt"],
    "draft": ["outline.md", "voice.md", "sources.md", "claims.json"],
    "revision": [],  # determined dynamically from section count
    "polish": [],  # determined dynamically
}

# Files produced by a phase (outputs)
PHASE_OUTPUTS = {
    "foundation": ["outline.md", "voice.md", "sources.md", "claims.json"],
    "draft": [],  # determined from outline section count
    "revision": [],  # updated in place
    "polish": ["final_article.md"],
}


def check_file(path_str: str, hints: list[str] | None, is_dir: bool = False) -> tuple[bool, str]:
    """Check a single file. Returns (ok, message)."""
    path = Path(path_str)

    if is_dir:
        if not path.exists():
            return False, f"Missing: {path_str}/"
        if not path.is_dir():
            return False, f"Not a directory: {path_str}/"
        md_files = list(path.glob("*.md"))
        if not md_files:
            return False, f"Empty directory: {path_str}/"
        return True, f"OK ({len(md_files)} files)"

    if not path.exists():
        return False, f"Missing: {path_str}"

    if not path.is_file():
        return False, f"Not a file: {path_str}"

    size = path.stat().st_size
    if size == 0:
        return False, f"Empty: {path_str}"

    if hints:
        content = path.read_text().lower()
        missing = [h for h in hints if h.lower() not in content]
        if missing:
            return False, f"{path_str}: missing expected content: {', '.join(missing)}"

    return True, f"OK ({size} bytes)"


def check_phase(phase: str, missing_only: bool = False) -> bool:
    """Check prerequisites for a phase. Returns True if all OK."""
    print(f"\n{'='*50}")
    print(f"CHECKING: {phase.upper()}")
    print(f"{'='*50}")

    requirements = PHASE_REQUIREMENTS.get(phase, {})

    # Also check inherited prerequisites
    inherited = {
        "draft": PHASE_REQUIREMENTS.get("foundation", {}),
        "revision": {**PHASE_REQUIREMENTS.get("foundation", {}), **PHASE_REQUIREMENTS.get("draft", {})},
        "polish": {**PHASE_REQUIREMENTS.get("foundation", {}), **PHASE_REQUIREMENTS.get("draft", {})},
    }
    all_req = {**inherited.get(phase, {}), **requirements}

    all_ok = True
    for file_path, value in all_req.items():
        # Skip None entries (placeholder for directory checks handled dynamically)
        if value is None:
            continue
        desc, hints = value
        is_dir = file_path == "sections"
        ok, msg = check_file(file_path, hints, is_dir=is_dir)
        status = "PASS" if ok else "FAIL"
        symbol = "✓" if ok else "✗"
        print(f"  [{symbol}] {status} {file_path:<20} {desc}")
        if not ok:
            all_ok = False

    # Phase-specific dynamic checks
    if phase == "draft":
        if Path("outline.md").exists():
            import re
            outline_text = Path("outline.md").read_text()
            # Count all ## headings (not ###) — captures ## Section N, ## N., ## Title
            section_count = len(re.findall(r'^## [^#]', outline_text, re.MULTILINE))
            print(f"  Sections found in outline: {section_count}")
            if section_count == 0:
                print(f"  [ ] FAIL outline has no sections")
                all_ok = False

    if phase == "revision":
        sections_dir = Path("sections")
        if sections_dir.exists():
            sections = sorted(sections_dir.glob("section_*.md"))
            print(f"  Drafted sections: {len(sections)}")
            if len(sections) == 0:
                print(f"  [ ] FAIL no drafted sections")
                all_ok = False

    if phase == "polish":
        sections_dir = Path("sections")
        if sections_dir.exists():
            sections = sorted(sections_dir.glob("section_*.md"))
            print(f"  Sections to assemble: {len(sections)}")

    return all_ok


def check_section_count() -> int:
    """Count sections from outline."""
    if not Path("outline.md").exists():
        return 0
    return Path("outline.md").read_text().count("## Section")


def main():
    parser = argparse.ArgumentParser(description="Check pipeline prerequisites")
    parser.add_argument("--phase", choices=["foundation", "draft", "revision", "polish", "all"])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if any check fails")
    args = parser.parse_args()

    phases = ["foundation", "draft", "revision", "polish"] if (args.all or args.phase == "all") else [args.phase]

    if not args.phase and not args.all:
        parser.print_help()
        print("\nPhases: foundation | draft | revision | polish | --all")
        sys.exit(0)

    results = {}
    for phase in phases:
        ok = check_phase(phase)
        results[phase] = ok

    print(f"\n{'='*50}")
    print("SUMMARY")
    print(f"{'='*50}")
    for phase, ok in results.items():
        symbol = "✓" if ok else "✗"
        print(f"  [{symbol}] {phase}")

    all_passed = all(results.values())
    if not all_passed and args.strict:
        print("\nStrict mode: exiting non-zero due to failures.")
        sys.exit(1)
    elif all_passed:
        print("\nAll checks passed.")
    else:
        print("\nSome checks failed. Fix before running pipeline.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Assemble sections into final article with LLM-guided transitions.

Two-pass approach:
  Pass 1 — Transition planner: reads all sections, generates bridging
           sentences between consecutive sections where needed.
  Pass 2 — Final assembler: combines section content with transitions,
           applies voice guide, removes cross-section repetition.

Usage:
    python build_final.py [--output final_article.md] [--no-llm]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from autoarticle.utils.api import api_post


# -------------------------------------------------------------------
# System prompts
# -------------------------------------------------------------------

TRANSITION_SYSTEM = """You are an expert editor. Your job is to plan transitions between independently-written article sections.

For each pair of consecutive sections, decide:
1. Does a transition sentence(s) need to be added between them?
2. If YES — write 1-2 bridging sentences that:
   - Echo the last idea of the previous section
   - Lead naturally into the first idea of the next section
   - Do NOT introduce new facts or claims
3. If NO — output exactly "NO_TRANSITION" for that boundary

Be conservative: transitions are needed only when the topic or tone shifts abruptly.
A smooth thematic continuation (same topic, next point) does NOT need a bridge."""

TRANSITION_USER = """Analyze these article sections and plan transitions between consecutive sections.

Title: {title}

Voice guide: {voice}

Sections (in order):
{sections}

For each boundary between sections, output:
  ---BOUNDARY N---
  [transition sentence(s) or NO_TRANSITION]

Keep transitions brief (1-2 sentences max). Do not repeat facts already stated."""

ASSEMBLY_SYSTEM = """You are an expert technical writer. Assemble independently-written sections into a single cohesive article.

Your rules:
- Output ONLY the final article text — no markers, no headers, no section labels
- Apply the voice guide consistently throughout
- Insert the provided transitions exactly as given
- If a transition is "NO_TRANSITION", join the sections directly (no bridge needed)
- Remove any repeated sentences or phrasings that appear across sections
- Do NOT rewrite section content — only connect, trim overlap, and enforce voice
- Strong closing paragraph that ties back to the opening"""

ASSEMBLY_USER = """Assemble these sections into a final polished article.

Title: {title}

Voice guide:
{voice}

Transitions between sections (may include NO_TRANSITION — join directly in that case):
{transitions}

Section content (in order):
{content}

Output the complete final article now."""


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def get_title() -> str:
    seed_path = Path("seed.txt")
    if seed_path.exists():
        for line in seed_path.read_text().splitlines():
            if line.startswith("title:"):
                return line.split(":", 1)[1].strip().strip('"')
    return ""


def get_voice(max_chars: int = 1200) -> str:
    voice_path = Path("voice.md")
    if voice_path.exists():
        return voice_path.read_text()[:max_chars]
    return ""


def get_outline(max_chars: int = 2000) -> str:
    outline_path = Path("outline.md")
    if outline_path.exists():
        return outline_path.read_text()[:max_chars]
    return ""


def load_sections(sections_dir: Path) -> list[tuple[str, str]]:
    """Return list of (filename, content) pairs, sorted by section number."""
    section_files = sorted(sections_dir.glob("section_*.md"))
    result = []
    for sf in section_files:
        content = sf.read_text().strip()
        if content:
            result.append((sf.name, content))
    return result


def parse_transitions(raw: str) -> list[str]:
    """Parse the transition planner output into a list of transition texts."""
    transitions = []
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("---BOUNDARY"):
            transitions.append("")
        elif transitions:
            if transitions[-1]:
                transitions[-1] += " " + stripped
            else:
                transitions[-1] = stripped
    return transitions


# -------------------------------------------------------------------
# Pass 1: Plan transitions
# -------------------------------------------------------------------

def plan_transitions(title: str, voice: str, sections: list[tuple[str, str]]) -> list[str]:
    """Ask LLM to decide where transitions are needed and what they should say."""
    if len(sections) < 2:
        return []

    # Format sections with markers so LLM can identify boundaries
    formatted = []
    for i, (fname, content) in enumerate(sections):
        formatted.append(f"\n=== SECTION {i + 1} ({fname}) ===\n{content}")
    sections_text = "\n".join(formatted)

    user_prompt = TRANSITION_USER.format(
        title=title,
        voice=voice,
        sections=sections_text,
    )

    raw = api_post(user_prompt, system=TRANSITION_SYSTEM, max_tokens=512)
    transitions = parse_transitions(raw)

    # Ensure we have the right number of transitions (one per boundary = len(sections) - 1)
    while len(transitions) < len(sections) - 1:
        transitions.append("NO_TRANSITION")
    transitions = transitions[: len(sections) - 1]

    print(f"  Transition plan: {sum(1 for t in transitions if t and t != 'NO_TRANSITION')}/{len(transitions)} bridges")
    return transitions


# -------------------------------------------------------------------
# Pass 2: Assemble final article
# -------------------------------------------------------------------

def assemble_llm(sections_dir: Path, output_path: Path) -> None:
    """Two-pass LLM assembly: plan transitions, then assemble."""
    sections = load_sections(sections_dir)
    if not sections:
        print("Error: no sections found")
        sys.exit(1)

    title = get_title()
    voice = get_voice()
    outline = get_outline()

    print(f"Assembling {len(sections)} sections with LLM (2-pass)...")

    # --- Pass 1: plan transitions ---
    print("  [Pass 1] Planning transitions...")
    transitions = plan_transitions(title, voice, sections)
    transition_str = "\n".join(
        f"Boundary {i + 1}: {t}" for i, t in enumerate(transitions)
    )

    # --- Pass 2: assemble final article ---
    print("  [Pass 2] Assembling final article...")
    content_blocks = []
    for fname, content in sections:
        content_blocks.append(f"[{fname}]\n{content}")
    content_str = "\n\n".join(content_blocks)

    user_prompt = ASSEMBLY_USER.format(
        title=title,
        voice=voice,
        transitions=transition_str,
        content=content_str,
    )

    result = api_post(user_prompt, system=ASSEMBLY_SYSTEM, max_tokens=2048)

    # Strip any leading markers the model might have emitted
    result = result.strip()
    # Remove any residual section markers
    import re
    result = re.sub(r"^\[section_\d+\]\s*", "", result, flags=re.IGNORECASE | re.MULTILINE)
    result = re.sub(r"^===\s*SECTION \d+\s*===\s*", "", result, flags=re.MULTILINE)
    result = result.strip()

    # Only append bibliography if it has real content
    bib_path = Path("bibliography.md")
    if bib_path.exists():
        bib_text = bib_path.read_text().strip()
        # Exclude the header line and placeholder
        meaningful_lines = [
            l for l in bib_text.splitlines()
            if l.strip()
            and not l.strip().startswith("#")
            and "no verified sources" not in l.lower()
            and l.strip() not in ("*No verified sources yet.*", "*No sources found.*")
        ]
        if meaningful_lines:
            result += "\n\n" + bib_text
            print(f"  Bibliography appended ({len(meaningful_lines)} entries)")
        else:
            print(f"  Bibliography skipped (empty placeholder)")

    output_path.write_text(result)
    print(f"Assembled → {output_path}")


# -------------------------------------------------------------------
# Direct concatenation (--no-llm fallback)
# -------------------------------------------------------------------

def assemble_direct(sections_dir: Path, output_path: Path) -> None:
    """Simple concatenation without LLM — fallback only."""
    sections = load_sections(sections_dir)
    title = get_title()

    lines = []
    if title:
        lines.extend([f"# {title}", ""])
    for _, content in sections:
        lines.extend([content, ""])

    output_path.write_text("\n\n".join(lines))
    print(f"Assembled {len(sections)} sections (direct) → {output_path}")


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Assemble final article")
    parser.add_argument("--output", default="final_article.md")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM assembly — simple concatenation only",
    )
    args = parser.parse_args()

    sections_dir = Path("sections")
    if not sections_dir.exists():
        print("Error: sections/ not found")
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.no_llm:
        assemble_direct(sections_dir, output_path)
    else:
        assemble_llm(sections_dir, output_path)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Generate outline.md from seed.txt.

Usage:
    python gen_outline.py [--seed seed.txt] [--output outline.md]
"""
import argparse
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from autoarticle.utils.api import api_post
from autoarticle.utils.state import load_state, save_state


ARTICLE_LENGTHS = {
    "short": "< 500 words",
    "medium": "500-1500 words",
    "long": "1500-3000 words",
    "feature": "3000+ words",
}

TYPE_STRUCTURES = {
    "explainer": [
        ("Hook", "Why should the reader care about this topic?"),
        ("What is it?", "Plain-language definition"),
        ("How does it work?", "Stepped explanation"),
        ("Why does it matter?", "Real-world significance"),
        ("Where is it going?", "Future outlook"),
    ],
    "howto": [
        ("Goal", "What the reader will accomplish"),
        ("Prerequisites", "What they need before starting"),
        ("Step 1", "First step"),
        ("Step 2", "Second step"),
        ("Step N...", "Additional steps as needed"),
        ("Troubleshooting", "Common failure modes"),
        ("Next steps", "Where to go after"),
    ],
    "project": [
        ("Motivation", "Why you built it, what problem it solves"),
        ("Approach", "Architecture, key decisions"),
        ("What went well", "Wins worth sharing"),
        ("What was hard", "Honest struggles"),
        ("Lessons", "What you'd do differently"),
        ("Links", "Code, demo, further reading"),
    ],
    "opinion": [
        ("The claim", "What you believe, stated clearly"),
        ("The reasoning", "Why you believe it"),
        ("Evidence", "Examples, data, experience"),
        ("Counterarguments", "Addressed honestly"),
        ("The takeaway", "What follows from your position"),
    ],
    "review": [
        ("What it is", "Concise — reader should already know"),
        ("What it does well", "Honest positives"),
        ("Where it falls short", "Honest negatives"),
        ("Who it's for", "And who should avoid it"),
        ("The verdict", "Buy/skip/conditional"),
    ],
    "news": [
        ("What happened", "Lead — most important first"),
        ("Who was involved", "Names, organizations"),
        ("When and where", "Timeline, location"),
        ("Why it matters", "Context"),
        ("What comes next", "Future developments"),
    ],
    "retrospective": [
        ("Setting the scene", "Context"),
        ("What happened", "The story"),
        ("What I learned", "Insights, hard-won"),
        ("Advice to past self", "What you'd tell yourself then"),
        ("Where it left me", "Conclusion"),
    ],
    "reference": [
        ("Overview", "What this is, scope"),
        ("Specification", "Technical details, tables"),
        ("Examples", "Annotated, runnable"),
        ("Edge cases", "Limits, error conditions"),
    ],
}


SYSTEM = """You are an expert technical writer. Generate a structured article outline from the provided seed information.

Output a markdown outline with the following format for EACH section:

## Section Title

**Key Claims (must cover in this section):**
- Claim 1
- Claim 2

**Target Length:** ~150-300 words

**Transition to next:** One sentence describing how this section flows into the next.

---

Be specific. Generic sections with vague claims are useless.
Each key claim should be a concrete statement about what this section must communicate.
If the article type is "howto", the steps should be specific and independently verifiable."""


def parse_seed(seed_path: Path) -> dict:
    """Parse seed.txt into a structured dict."""
    content = seed_path.read_text()
    result = {}
    current_key = None
    current_value = []

    for line in content.splitlines():
        line = line.rstrip()
        if not line:
            continue
        colon_pos = line.find(":")
        is_new_key = (
            colon_pos > 0
            and not line.startswith(" ")
            and not line.startswith("#")
            and not line.startswith("-")
            and not line.startswith("*")
        )
        if is_new_key:
            if current_key:
                result[current_key] = "\n".join(current_value).strip()
            key = line[:colon_pos].strip()
            value = line[colon_pos + 1 :].strip()
            current_key = key
            current_value = [value] if value else []
        else:
            if line.strip() and current_key is not None:
                current_value.append(line)

    if current_key:
        result[current_key] = "\n".join(current_value).strip()
    return result


def main():
    parser = argparse.ArgumentParser(description="Generate outline from seed")
    parser.add_argument("--seed", default="seed.txt", help="Seed file path")
    parser.add_argument("--output", default="outline.md", help="Output file path")
    args = parser.parse_args()

    seed_path = Path(args.seed)
    if not seed_path.exists():
        print(f"Error: seed file not found: {seed_path}")
        sys.exit(1)

    seed = parse_seed(seed_path)
    print(f"Article: {seed.get('title', 'Untitled')}")
    print(f"Type: {seed.get('type', 'unknown')}")

    # Build user prompt
    article_type = seed.get("type", "explainer").strip().lower()
    title = seed.get("title", "Untitled").strip()
    length = seed.get("target_length", "medium").strip().lower()
    tone = seed.get("tone", "semiformal").strip().lower()
    audience = seed.get("audience", "intermediate").strip().lower()
    bullets = [b.strip() for b in seed.get("seed_bullets", "").splitlines() if b.strip()]
    examples = [e.strip() for e in seed.get("examples", "").splitlines() if e.strip()]

    length_desc = ARTICLE_LENGTHS.get(length, "medium (500-1500 words)")
    structure = TYPE_STRUCTURES.get(article_type, TYPE_STRUCTURES["explainer"])
    structure_text = "\n".join(f"  {i+1}. {n}: {h}" for i, (n, h) in enumerate(structure))

    # Skip Links section if no sources required
    include_sources = seed.get("include_sources", "basic").strip().lower()
    if include_sources == "none":
        structure_text += "\n  (Do NOT include a Links/Resources/Further Reading section — this article has include_sources: none)"

    prompt = f"""Generate an article outline.

## Article Specification

**Title:** {title}
**Type:** {article_type}
**Target Length:** {length_desc}
**Tone:** {tone}
**Audience:** {audience}

## Seed Thoughts

{chr(10).join(f"- {b}" for b in bullets)}

## Style Examples

{chr(10).join(f"- {e}" for e in examples) if examples else "(no examples)"}

## Section Structure for "{article_type}"

{structure_text}

---

IMPORTANT: Adapt sections to fit the actual content. Add, remove, or merge sections as needed. Be specific about what each section must cover."""

    print("Generating outline...")
    outline = api_post(prompt, system=SYSTEM, max_tokens=2048)

    output_path = Path(args.output)
    output_path.write_text(outline)
    print(f"Outline written to: {output_path}")

    # Update state
    state_path = Path("state.json")
    if state_path.exists():
        state = load_state()
        state["iteration"] = state.get("iteration", 0) + 1
        save_state(state)


if __name__ == "__main__":
    main()

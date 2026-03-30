#!/usr/bin/env python3
"""
Generate outline.md from seed.txt.

Reads seed.txt (type, title, length, tone, audience, seed_bullets, examples),
then calls the LLM to generate a structured outline with sections and key claims.

Usage:
    python gen_outline.py [--seed seed.txt]
Output: outline.md
"""
import argparse
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from autoarticle.utils.config import load_config
from autoarticle.utils.state import load_state, save_state

import httpx


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


SYSTEM_PROMPT = """You are an expert technical writer. Generate a structured article outline from the provided seed information.

Output a markdown outline with the following format for EACH section:

## Section Title

**Key Claims (must cover in this section):**
- Claim 1
- Claim 2

**Target Length:** ~150-300 words

**Transition to next:** One sentence describing how this section flows into the next.

---

Be specific. Generic sections with vague claims are useless.
Each key claim should be a concrete statement about what this section must communicate — not a topic heading.

If the article type is "howto", the steps should be specific and independently verifiable.

If examples were provided, use them to calibrate the right depth and tone for the target audience."""


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

        # Look for key: value
        if ": " in line and not line.startswith(" "):
            # Save previous key
            if current_key:
                result[current_key] = "\n".join(current_value).strip()

            key, _, value = line.partition(": ")
            current_key = key.strip()
            current_value = [value] if value else []
        else:
            # Continuation of previous key
            current_value.append(line)

    if current_key:
        result[current_key] = "\n".join(current_value).strip()

    return result


def build_prompt(seed: dict) -> str:
    """Build the full prompt for outline generation."""
    article_type = seed.get("type", "explainer").strip().lower()
    title = seed.get("title", "Untitled").strip()
    length = seed.get("target_length", "medium").strip().lower()
    tone = seed.get("tone", "semiformal").strip().lower()
    audience = seed.get("audience", "intermediate").strip().lower()
    bullets_raw = seed.get("seed_bullets", "")
    examples_raw = seed.get("examples", "")

    bullets = [b.strip() for b in bullets_raw.strip().splitlines() if b.strip()]
    examples = [e.strip() for e in examples_raw.strip().splitlines() if e.strip()]

    length_desc = ARTICLE_LENGTHS.get(length, "medium (500-1500 words)")
    structure = TYPE_STRUCTURES.get(article_type, TYPE_STRUCTURES["explainer"])

    # Format structure as guidance
    structure_text = "\n".join(
        f"  {i+1}. {name}: {hint}" for i, (name, hint) in enumerate(structure)
    )

    user_prompt = f"""Generate an article outline.

## Article Specification

**Title:** {title}
**Type:** {article_type}
**Target Length:** {length_desc}
**Tone:** {tone}
**Audience:** {audience}

## Seed Thoughts (raw material to organize into sections)

{chr(10).join(f"- {b}" for b in bullets)}

## Style Examples (use these to calibrate depth and voice)

{chr(10).join(f"- {e}" for e in examples) if examples else "(no examples provided)"}

## Suggested Section Structure for "{article_type}" type

{structure_text}

---

IMPORTANT:
- Adapt the section structure above to fit the actual content from seed thoughts
- Do NOT force content into sections that don't naturally fit
- Add, remove, or merge sections as the content demands
- Be specific about what each section must cover (key claims)
- Estimate realistic word counts per section based on target length
"""

    return f"{SYSTEM_PROMPT}\n\n{user_prompt}"


def call_llm(prompt: str, config: dict) -> str:
    """Call Anthropic API to generate outline."""
    client = httpx.Client(timeout=60)

    response = client.post(
        f"{config['api_base_url']}/v1/messages",
        headers={
            "x-api-key": config["anthropic_api_key"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": config["writer_model"],
            "max_tokens": 2048,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        },
    )

    if response.status_code != 200:
        raise RuntimeError(f"API error: {response.status_code} {response.text}")

    data = response.json()
    return data["content"][0]["text"]


def generate_outline(seed_path: Path, output_path: Path) -> None:
    """Main entry point."""
    print(f"Reading seed from: {seed_path}")
    seed = parse_seed(seed_path)

    print(f"Article: {seed.get('title', 'Untitled')}")
    print(f"Type: {seed.get('type', 'unknown')}")
    print(f"Target length: {seed.get('target_length', 'medium')}")

    config = load_config()
    config_dict = {
        "anthropic_api_key": config.anthropic_api_key,
        "writer_model": config.writer_model,
        "api_base_url": config.api_base_url,
    }

    print("Generating outline...")
    prompt = build_prompt(seed)
    outline = call_llm(prompt, config_dict)

    output_path.write_text(outline)
    print(f"Outline written to: {output_path}")

    # Update state if state.json exists
    state_path = Path("state.json")
    if state_path.exists():
        state = load_state()
        state["iteration"] = state.get("iteration", 0) + 1
        save_state(state)


def main():
    parser = argparse.ArgumentParser(description="Generate outline from seed")
    parser.add_argument("--seed", default="seed.txt", help="Seed file path")
    parser.add_argument("--output", default="outline.md", help="Output file path")
    args = parser.parse_args()

    seed_path = Path(args.seed)
    if not seed_path.exists():
        print(f"Error: seed file not found: {seed_path}")
        sys.exit(1)

    output_path = Path(args.output)
    generate_outline(seed_path, output_path)


if __name__ == "__main__":
    main()

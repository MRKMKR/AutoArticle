#!/usr/bin/env python3
"""
Assemble sections into final article output.

Usage:
    python build_final.py [--output final_article.md]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from autoarticle.utils.config import load_config

import httpx


def build_prompt(seed_title: str, sections_text: str, outline: str, voice: str, config) -> str:
    return f"""Assemble these article sections into a final polished article.

The output should:
1. Have a title derived from: {seed_title}
2. Open with a strong hook paragraph
3. Flow naturally between sections (add transition sentences only where needed)
4. End with a conclusion that reinforces the main point

Do NOT repeat content between sections. Do NOT add new content. Only assemble and connect.

Voice guide to follow:
{voice[:1000]}

Sections (in order):
{sections_text}

Outline:
{outline[:2000]}

Output ONLY the final article — no headers, no markers. Start directly with the title or intro paragraph."""


def call_llm(prompt: str, config) -> str:
    client = httpx.Client(timeout=120)
    response = client.post(
        f"{config.api_base_url}/v1/messages",
        headers={
            "x-api-key": config.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": config.writer_model,
            "max_tokens": 4096,
            "system": "You are an expert technical writer. Assemble sections into a cohesive final article.",
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    if response.status_code != 200:
        raise RuntimeError(f"API error: {response.status_code} {response.text}")
    return response.json()["content"][0]["text"]


def assemble_direct(sections_dir: Path, output_path: Path) -> None:
    """Assemble sections directly without LLM — faster, no API needed."""
    section_files = sorted(sections_dir.glob("section_*.md"))
    if not section_files:
        raise ValueError("No sections found")

    parts = []
    for sf in section_files:
        content = sf.read_text().strip()
        if content:
            parts.append(content)

    # Add title from seed
    title = ""
    seed_path = Path("seed.txt")
    if seed_path.exists():
        seed_content = seed_path.read_text()
        for line in seed_content.splitlines():
            if line.startswith("title:"):
                title = line.split(":", 1)[1].strip().strip('"')
                break

    lines = []
    if title:
        lines.append(f"# {title}")
        lines.append("")
    lines.extend(parts)

    output_path.write_text("\n\n".join(lines))
    print(f"Assembled {len(section_files)} sections → {output_path}")


def assemble_llm(sections_dir: Path, output_path: Path, config) -> None:
    """Assemble sections using LLM for smoother transitions."""
    section_files = sorted(sections_dir.glob("section_*.md"))
    if not section_files:
        raise ValueError("No sections found")

    sections_text = []
    for sf in section_files:
        content = sf.read_text().strip()
        if content:
            sections_text.append(f"--- {sf.name} ---\n{content}")

    seed_title = ""
    seed_path = Path("seed.txt")
    if seed_path.exists():
        for line in seed_path.read_text().splitlines():
            if line.startswith("title:"):
                seed_title = line.split(":", 1)[1].strip().strip('"')
                break

    outline = Path("outline.md").read_text() if Path("outline.md").exists() else ""
    voice = Path("voice.md").read_text() if Path("voice.md").exists() else ""

    prompt = build_prompt(seed_title, "\n\n".join(sections_text), outline, voice, config)

    print(f"Assembling {len(section_files)} sections with LLM...")
    result = call_llm(prompt, config)

    output_path.write_text(result)
    print(f"Assembled → {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Assemble sections into final article")
    parser.add_argument("--output", default="final_article.md", help="Output file")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM assembly (direct concatenation)")
    args = parser.parse_args()

    sections_dir = Path("sections")
    if not sections_dir.exists():
        print("Error: sections/ directory not found")
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.no_llm:
        assemble_direct(sections_dir, output_path)
    else:
        config = load_config()
        assemble_llm(sections_dir, output_path, config)


if __name__ == "__main__":
    main()

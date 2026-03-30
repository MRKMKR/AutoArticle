#!/usr/bin/env python3
"""
Assemble sections into final article.

Usage:
    python build_final.py [--output final_article.md] [--no-llm]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from autoarticle.utils.api import api_post


SYSTEM = """You are an expert technical writer. Assemble sections into a cohesive final article.

Rules:
- Strong hook opening paragraph
- Natural transitions between sections (add only where needed)
- No repetition between sections
- No new content — only connect and polish
- End with a conclusion reinforcing the main point
- Output ONLY the final article — no headers, no markers"""


def assemble_direct(sections_dir: Path, output_path: Path) -> None:
    section_files = sorted(sections_dir.glob("section_*.md"))
    parts = [sf.read_text().strip() for sf in section_files if sf.read_text().strip()]

    title = ""
    seed_path = Path("seed.txt")
    if seed_path.exists():
        for line in seed_path.read_text().splitlines():
            if line.startswith("title:"):
                title = line.split(":", 1)[1].strip().strip('"')
                break

    lines = []
    if title:
        lines.extend([f"# {title}", ""])
    lines.extend(parts)

    output_path.write_text("\n\n".join(lines))
    print(f"Assembled {len(section_files)} sections → {output_path}")


def assemble_llm(sections_dir: Path, output_path: Path) -> None:
    section_files = sorted(sections_dir.glob("section_*.md"))
    sections_text = "\n\n".join(f"--- {sf.name} ---\n{sf.read_text().strip()}" for sf in section_files if sf.read_text().strip())

    title = ""
    seed_path = Path("seed.txt")
    if seed_path.exists():
        for line in seed_path.read_text().splitlines():
            if line.startswith("title:"):
                title = line.split(":", 1)[1].strip().strip('"')
                break

    outline = Path("outline.md").read_text()[:2000] if Path("outline.md").exists() else ""
    voice = Path("voice.md").read_text()[:1000] if Path("voice.md").exists() else ""

    prompt = f"""Assemble these article sections into a final polished article.

Title: {title}

Voice guide:
{voice}

Outline:
{outline}

Sections:
{sections_text}

Output ONLY the final article — start directly with the title or intro paragraph."""

    print(f"Assembling {len(section_files)} sections with LLM...")
    result = api_post(prompt, system=SYSTEM, max_tokens=4096)
    output_path.write_text(result)
    print(f"Assembled → {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Assemble final article")
    parser.add_argument("--output", default="final_article.md")
    parser.add_argument("--no-llm", action="store_true")
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

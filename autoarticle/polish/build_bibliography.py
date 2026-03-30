#!/usr/bin/env python3
"""
Build bibliography from claims.json and sources.md.

Usage:
    python build_bibliography.py [--claims claims.json] [--sources sources.md] [--output bibliography.md] [--style apa|ieee|chicago]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


CITE_STYLES = {
    "apa": {
        "article": "{authors} ({year}). {title}. {journal}, {volume}({issue}), {pages}. {url}",
        "book": "{authors} ({year}). {title}. {publisher}.",
        "web": "{authors} ({year}). {title}. Retrieved from {url}",
        "default": "{authors} ({year}). {title}. {url}",
    },
    "ieee": {
        "article": "[{num}] {authors}, \"{title},\" {journal}, vol. {volume}, no. {issue}, pp. {pages}, {year}.",
        "book": "[{num}] {authors}, {title}. {publisher}, {year}.",
        "web": "[{num}] {authors}, \"{title}.\" [Online]. Available: {url}",
        "default": "[{num}] {authors}, \"{title}.\" {url}",
    },
    "chicago": {
        "article": '{authors}. "{title}." {journal} {volume}, no. {issue} ({year}): {pages}. {url}.',
        "book": "{authors}. {title}. {publisher}, {year}.",
        "web": '{authors}. "{title}." Accessed: {access_date}. {url}.',
        "default": "{authors}. \"{title}.\" {url}.",
    },
}


def parse_source_type(source_hint: str) -> str:
    """Guess source type from hint text."""
    hint = source_hint.lower()
    if "journal" in hint or "paper" in hint or "arxiv" in hint:
        return "article"
    if "book" in hint or "o'reilly" in hint:
        return "book"
    if "http" in hint or "url" in hint or "website" in hint or "blog" in hint:
        return "web"
    return "default"


def format_citation(source: dict, style: str = "apa") -> str:
    """Format a single citation in the given style."""
    style_templates = CITE_STYLES.get(style, CITE_STYLES["apa"])
    source_type = source.get("type", "default")
    template = style_templates.get(source_type, style_templates["default"])

    # Fill in template
    result = template
    for key, value in source.items():
        result = result.replace(f"{{{key}}}", str(value))

    return result


def build_bibliography(claims: list, sources: str, output_path: Path, style: str) -> None:
    """Build bibliography from claims and sources."""
    # Find all verified claims with sources
    verified = [c for c in claims if c.get("verified") and c.get("source")]

    if not verified:
        output_path.write_text("# Bibliography\n\n*No verified sources yet.*\n")
        print(f"No verified sources found. Empty bibliography written to {output_path}")
        return

    # Parse sources.md to get citation data
    # For now, use the source URL and hint as the citation
    source_entries = []
    for c in verified:
        source_hint = c.get("source_hint", "")
        url = c.get("source", "")
        source_type = parse_source_type(source_hint)

        entry = {
            "type": source_type,
            "title": c.get("text", "")[:100],  # Use claim text as title proxy
            "url": url,
            "authors": source_hint.split(",")[0].strip() if "," in source_hint else source_hint.strip(),
            "year": "",  # Would need date parsing
        }
        source_entries.append(entry)

    # Remove duplicates by URL
    seen_urls = set()
    unique = []
    for e in source_entries:
        if e["url"] and e["url"] not in seen_urls:
            seen_urls.add(e["url"])
            unique.append(e)

    # Format citations
    citations = []
    for i, entry in enumerate(unique, 1):
        entry["num"] = i
        citation = format_citation(entry, style)
        citations.append(citation)

    # Write bibliography
    lines = [f"# Bibliography\n"]
    for i, cite in enumerate(citations, 1):
        lines.append(f"[{i}] {cite}")

    output_path.write_text("\n".join(lines))
    print(f"Bibliography ({len(citations)} sources) written to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Build bibliography from claims")
    parser.add_argument("--claims", default="claims.json")
    parser.add_argument("--sources", default="sources.md")
    parser.add_argument("--output", default="bibliography.md")
    parser.add_argument("--style", default="apa", choices=["apa", "ieee", "chicago"])
    args = parser.parse_args()

    claims_path = Path(args.claims)
    sources_path = Path(args.sources)
    output_path = Path(args.output)

    claims = []
    if claims_path.exists():
        claims = json.loads(claims_path.read_text())

    sources = sources_path.read_text() if sources_path.exists() else ""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    build_bibliography(claims, sources, output_path, args.style)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Build bibliography from claims.json.

Usage:
    python build_bibliography.py [--claims claims.json] [--output bibliography.md] [--style apa|ieee|chicago]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


STYLES = {
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


def source_type(hint: str) -> str:
    h = hint.lower()
    if "journal" in h or "paper" in h or "arxiv" in h:
        return "article"
    if "book" in h or "o'reilly" in h:
        return "book"
    if "http" in h or "url" in h or "website" in h or "blog" in h:
        return "web"
    return "default"


def format_cite(entry: dict, style: str) -> str:
    templates = STYLES.get(style, STYLES["apa"])
    tpl = templates.get(entry.get("type", "default"), templates["default"])
    result = tpl
    for k, v in entry.items():
        result = result.replace(f"{{{k}}}", str(v))
    return result


def main():
    parser = argparse.ArgumentParser(description="Build bibliography")
    parser.add_argument("--claims", default="claims.json")
    parser.add_argument("--output", default="bibliography.md")
    parser.add_argument("--style", default="apa", choices=["apa", "ieee", "chicago"])
    args = parser.parse_args()

    claims_path = Path(args.claims)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    claims = json.loads(claims_path.read_text()) if claims_path.exists() else []
    verified = [c for c in claims if c.get("verified") and c.get("source")]

    if not verified:
        output_path.write_text("# Bibliography\n\n*No verified sources yet.*\n")
        print("No verified sources. Empty bibliography written.")
        return

    entries = []
    seen = set()
    for c in verified:
        url = c.get("source", "")
        if url and url not in seen:
            seen.add(url)
            hint = c.get("source_hint", "")
            entries.append({
                "type": source_type(hint),
                "title": c.get("text", "")[:100],
                "url": url,
                "authors": hint.split(",")[0].strip() if "," in hint else hint.strip(),
                "year": "",
                "num": len(entries) + 1,
            })

    lines = ["# Bibliography"]
    for e in entries:
        lines.append(f"[{e['num']}] {format_cite(e, args.style)}")

    output_path.write_text("\n".join(lines))
    print(f"Bibliography ({len(entries)} sources) → {output_path}")


if __name__ == "__main__":
    main()

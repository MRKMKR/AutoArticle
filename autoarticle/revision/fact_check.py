#!/usr/bin/env python3
"""
Fact-check claims against sources.

Usage:
    python fact_check.py --claim N
    python fact_check.py --all
    python fact_check.py --cite <id> <url>
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from autoarticle.utils.api import api_post


SYSTEM = """You are a research fact-checker. Be precise about what can and cannot be verified.

Respond with ONLY valid JSON:
{
  "verifiable": true/false,
  "confidence": "high/medium/low",
  "verdict": "supported/unsupported/needs_verification",
  "reason": "brief explanation",
  "suggested_source": "what source would verify this"
}"""


def parse_json(raw: str) -> dict:
    import re
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"```\s*$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"verifiable": False, "confidence": "low", "verdict": "needs_verification",
                "reason": "parse error", "suggested_source": ""}


def load_claims(path: Path) -> list:
    if path.exists():
        return json.loads(path.read_text())
    return []


def save_claims(path: Path, claims: list) -> None:
    path.write_text(json.dumps(claims, indent=2))


def print_table(claims: list) -> None:
    print(f"\n{'='*60}")
    print("CLAIMS STATUS")
    print(f"{'='*60}")
    print(f"{'ID':<6} {'Section':<14} {'Verified':<10} {'Confidence':<10} Claim")
    print("-" * 60)
    for c in claims:
        status = "✓" if c.get("verified") else "✗"
        conf = c.get("confidence", "-")[:9]
        section = c.get("section", "-")[:13]
        text = c.get("text", "")[:35]
        print(f"{c.get('id','-'):<6} {section:<14} {status:<10} {conf:<10} {text}")


def main():
    parser = argparse.ArgumentParser(description="Fact-check claims")
    parser.add_argument("--claim", type=int, help="Check specific claim by ID")
    parser.add_argument("--claims", default="claims.json")
    parser.add_argument("--all", action="store_true", help="Check all unverified")
    parser.add_argument("--cite", nargs=2, metavar=("ID", "URL"), help="Add citation to claim")
    args = parser.parse_args()

    claims_path = Path(args.claims)
    claims = load_claims(claims_path)

    if args.cite:
        cid, url = args.cite
        found = False
        for c in claims:
            if c.get("id") == cid or c.get("id") == f"c{int(cid):02d}":
                c["verified"] = True
                c["source"] = url
                found = True
                print(f"Added citation to {c.get('id')}: {url}")
        if not found:
            print(f"Error: claim {cid} not found")
            sys.exit(1)
        save_claims(claims_path, claims)
        return

    if args.all or args.claim:
        if not claims:
            print(f"Error: no claims in {claims_path}. Run gen_claims.py first.")
            sys.exit(1)

        if args.claim:
            target = next((c for c in claims if c.get("id") == f"c{args.claim:02d}"), None)
            if not target:
                print(f"Error: claim c{args.claim:02d} not found")
                sys.exit(1)
            print(f"Checking: {target.get('text', '')[:80]}")
            result = parse_json(api_post(
                f"Claim: {target.get('text', '')}\nHint: {target.get('source_hint', '')}",
                system=SYSTEM, max_tokens=512
            ))
            print(f"Result: {result.get('verdict')} ({result.get('confidence')})")
            print(f"Reason: {result.get('reason')}")
            target["verified"] = result.get("verdict") == "supported"
            target["confidence"] = result.get("confidence")
            save_claims(claims_path, claims)
        else:
            unverified = [c for c in claims if not c.get("verified")]
            print(f"Checking {len(unverified)} unverified claims...")
            for c in unverified:
                cid = c.get("id", "?")
                print(f"  [{cid}] ", end="", flush=True)
                result = parse_json(api_post(
                    f"Claim: {c.get('text', '')}\nHint: {c.get('source_hint', '')}",
                    system=SYSTEM, max_tokens=512
                ))
                c["verified"] = result.get("verdict") == "supported"
                c["confidence"] = result.get("confidence")
                c["reason"] = result.get("reason")
                c["suggested_source"] = result.get("suggested_source")
                status = "✓" if c["verified"] else "✗"
                print(f"{status} — {result.get('verdict')}")
            save_claims(claims_path, claims)
            print_table(claims)
            v = sum(1 for c in claims if c.get("verified"))
            print(f"\nVerified: {v}/{len(claims)} ({v*100//len(claims)}%)")
    else:
        if not claims:
            print(f"No claims file at {claims_path}. Run gen_claims.py first.")
            sys.exit(1)
        print_table(claims)


if __name__ == "__main__":
    main()

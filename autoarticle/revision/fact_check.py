#!/usr/bin/env python3
"""
Fact-check claims against sources.

Usage:
    python fact_check.py --claim <id> [--claims claims.json]
    python fact_check.py --all
    python fact_check.py --cite <claim_id> <source_url>
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from autoarticle.utils.config import load_config

import httpx


def check_claim_claim(claim_text: str, source_hint: str, config) -> dict:
    """Use LLM to verify a claim against a source hint."""
    prompt = f"""Verify this factual claim. You do NOT have access to external sources.
Assess whether this claim is likely verifiable and how strong the evidence is.

Claim: {claim_text}
Suggested source type: {source_hint}

Respond with JSON:
{{
  "verifiable": true/false,
  "confidence": "high/medium/low",
  "verdict": "supported/unsupported/needs_verification",
  "reason": "brief explanation",
  "suggested_source": "what kind of source would verify this"
}}
"""
    client = httpx.Client(timeout=60)
    response = client.post(
        f"{config.api_base_url}/v1/messages",
        headers={
            "x-api-key": config.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": config.judge_model,
            "max_tokens": 512,
            "system": "You are a research fact-checker. Be precise about what can and cannot be verified.",
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    if response.status_code != 200:
        raise RuntimeError(f"API error: {response.status_code} {response.text}")

    import re
    raw = response.json()["content"][0]["text"]
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"```\s*$", "", raw)
    return json.loads(raw)


def load_claims(path: Path) -> list:
    if path.exists():
        return json.loads(path.read_text())
    return []


def save_claims(path: Path, claims: list) -> None:
    path.write_text(json.dumps(claims, indent=2))


def print_claims_table(claims: list) -> None:
    """Print a table of all claims and their verification status."""
    print(f"\n{'='*60}")
    print("CLAIMS STATUS")
    print(f"{'='*60}")
    print(f"{'ID':<6} {'Section':<15} {'Verified':<10} {'Confidence':<10} Claim")
    print("-" * 60)
    for c in claims:
        status = "✓" if c.get("verified") else "✗"
        conf = c.get("confidence", "-")[:9]
        section = c.get("section", "-")[:14]
        text = c.get("text", "")[:35]
        print(f"{c.get('id','-'):<6} {section:<15} {status:<10} {conf:<10} {text}")


def main():
    parser = argparse.ArgumentParser(description="Fact-check claims against sources")
    parser.add_argument("--claim", type=int, help="Check specific claim by ID number")
    parser.add_argument("--claims", default="claims.json", help="Claims file")
    parser.add_argument("--all", action="store_true", help="Check all unverified claims")
    parser.add_argument("--cite", nargs=2, metavar=("ID", "URL"), help="Add citation to claim")
    args = parser.parse_args()

    claims_path = Path(args.claims)
    config = load_config()

    if args.cite:
        # Add citation to a specific claim
        claim_id, url = args.cite
        claims = load_claims(claims_path)
        found = False
        for c in claims:
            if c.get("id") == claim_id or c.get("id") == f"c{int(claim_id):02d}":
                c["verified"] = True
                c["source"] = url
                found = True
                print(f"Added citation to {c.get('id')}: {url}")
        if not found:
            print(f"Error: claim {claim_id} not found")
            sys.exit(1)
        save_claims(claims_path, claims)
        return

    if args.all or args.claim:
        claims = load_claims(claims_path)
        if not claims:
            print(f"Error: no claims found in {claims_path}")
            print("Run gen_claims.py first to extract claims from the outline.")
            sys.exit(1)

        if args.claim:
            # Check specific claim
            target = None
            for c in claims:
                if c.get("id") == f"c{args.claim:02d}":
                    target = c
                    break
            if not target:
                print(f"Error: claim c{args.claim:02d} not found")
                sys.exit(1)
            print(f"Checking: {target.get('text', '')[:80]}")
            result = check_claim_claim(target.get("text", ""), target.get("source_hint", ""), config)
            print(f"\nResult: {result.get('verdict')}")
            print(f"Confidence: {result.get('confidence')}")
            print(f"Reason: {result.get('reason')}")
            print(f"Suggested source: {result.get('suggested_source')}")

            # Update claim
            target["verified"] = result.get("verdict") == "supported"
            target["confidence"] = result.get("confidence")
            save_claims(claims_path, claims)
        else:
            # Check all unverified
            unverified = [c for c in claims if not c.get("verified")]
            print(f"Checking {len(unverified)} unverified claims...")

            results = {}
            for c in unverified:
                cid = c.get("id", "?")
                print(f"  [{cid}] ", end="", flush=True)
                result = check_claim_claim(c.get("text", ""), c.get("source_hint", ""), config)
                results[cid] = result
                c["verified"] = result.get("verdict") == "supported"
                c["confidence"] = result.get("confidence")
                c["reason"] = result.get("reason")
                c["suggested_source"] = result.get("suggested_source")
                status = "✓" if c["verified"] else "✗"
                print(f"{status} ({result.get('confidence')}) — {result.get('verdict')}")

            save_claims(claims_path, claims)
            print_claims_table(claims)

            verified_count = sum(1 for c in claims if c.get("verified"))
            print(f"\nVerified: {verified_count}/{len(claims)} ({verified_count/len(claims)*100:.0f}%)")

    else:
        # Default: show current status
        claims = load_claims(claims_path)
        if not claims:
            print(f"No claims file at {claims_path}")
            print("Run gen_claims.py first to extract claims.")
            sys.exit(1)
        print_claims_table(claims)


if __name__ == "__main__":
    main()

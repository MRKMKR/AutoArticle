#!/usr/bin/env python3
"""
State management for AutoArticle pipeline.
Reads and writes state.json for per-article tracking.
"""
import json
import sys
from pathlib import Path


def get_state_path() -> Path:
    return Path("state.json")


def load_state() -> dict:
    path = get_state_path()
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {
        "phase": "foundation",
        "iteration": 0,
        "debts": [],
        "scores": {
            "foundation": None,
            "draft": {},
            "revision": {
                "cycle": 0,
                "clarity": None,
                "conciseness": None,
                "technical": None,
                "sources": None,
                "slop": None,
            },
        },
    }


def save_state(state: dict) -> None:
    path = get_state_path()
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def advance_phase(phase: str) -> None:
    state = load_state()
    state["phase"] = phase
    save_state(state)
    print(f"Phase advanced to: {phase}")


def add_debt(trigger: str, affected: list[str], status: str = "pending") -> None:
    state = load_state()
    state["debts"].append({
        "trigger": trigger,
        "affected": affected,
        "status": status,
    })
    save_state(state)


def resolve_debt(trigger: str) -> None:
    state = load_state()
    for debt in state["debts"]:
        if debt["trigger"] == trigger:
            debt["status"] = "resolved"
    save_state(state)


def log_result(
    phase: str,
    section: str,
    score: float,
    dimension: str,
    action: str,
    details: str,
) -> None:
    import datetime

    path = Path("results.tsv")
    row = [
        datetime.date.today().isoformat(),
        phase,
        section,
        f"{score:.1f}",
        dimension,
        action,
        details,
    ]
    with open(path, "a") as f:
        f.write("\t".join(row) + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: state.py <command> [args]")
        print("Commands: get, set-phase <phase>, add-debt <trigger>, log <score> <dim> <action> <details>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "get":
        print(json.dumps(load_state(), indent=2))
    elif cmd == "set-phase" and len(sys.argv) >= 3:
        advance_phase(sys.argv[2])
    elif cmd == "add-debt" and len(sys.argv) >= 4:
        add_debt(sys.argv[2], json.loads(sys.argv[3]))
    elif cmd == "log" and len(sys.argv) >= 7:
        log_result(sys.argv[2], sys.argv[3], float(sys.argv[4]), sys.argv[5], sys.argv[6], sys.argv[7])
    else:
        print("Unknown command or missing args")
        sys.exit(1)

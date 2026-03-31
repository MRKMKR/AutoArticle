#!/usr/bin/env python3
"""
AutoArticle Pipeline Orchestrator

Ties all phases together: foundation → draft → revision (loop) → polish.

Usage:
    python run_pipeline.py --phase foundation      # Run single phase
    python run_pipeline.py --all                   # Run full pipeline
    python run_pipeline.py --continue             # Resume from last phase
    python run_pipeline.py --check                 # Validate prerequisites only
    python run_pipeline.py --dry-run               # Show what would run

Environment:
    AUTOARTICLE_WORKDIR  Directory to run in (default: current dir)
    AUTOARTICLE_MAX_REVISION_CYCLES  Max revision loops (default: 3, with restore-on-degradation)
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path


WORKDIR = Path(os.environ.get("AUTOARTICLE_WORKDIR", ".")).resolve()
MAX_REVISION_CYCLES = int(os.environ.get("AUTOARTICLE_MAX_REVISION_CYCLES", "3"))

# Colour codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
GREY = "\033[90m"
BOLD = "\033[1m"
RESET = "\033[0m"


def cprint(text: str, colour: str = RESET) -> None:
    print(f"{colour}{text}{RESET}")


def heading(text: str) -> None:
    cprint(f"\n{'='*60}", CYAN)
    cprint(f"  {text}", CYAN + BOLD)
    cprint(f"{'='*60}\n", CYAN)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command, printing what it is."""
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    kwargs.setdefault("check", False)
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    result = subprocess.run(cmd, **kwargs)
    return result


def run_python(script_path: str, extra_args: list[str] | None = None, cwd: Path = WORKDIR) -> bool:
    """Run a Python script via uv, returns success."""
    cmd = ["uv", "run", "python", script_path]
    if extra_args:
        cmd.extend(extra_args)
    result = run(cmd, cwd=cwd)
    if result.returncode != 0 and result.stdout:
        print(f"  {RED}stdout:{RESET} {result.stdout[:500]}")
    if result.returncode != 0 and result.stderr:
        print(f"  {RED}stderr:{RESET} {result.stderr[:500]}")
    ok = result.returncode == 0
    cprint(f"  {'✓ PASS' if ok else '✗ FAIL'} (exit {result.returncode})", GREEN if ok else RED)
    return ok


def count_outline_sections() -> int:
    """Count sections in outline. Handles both '## Section N' and '## N.' formats."""
    import re
    outline = WORKDIR / "outline.md"
    if not outline.exists():
        return 0
    text = outline.read_text()
    # Count all ## headings (not ###) — handles ## Section N, ## N., ## Title
    return len(re.findall(r'^## [^#]', text, re.MULTILINE))


def count_sections() -> int:
    """Count drafted sections."""
    sections_dir = WORKDIR / "sections"
    if not sections_dir.exists():
        return 0
    return len(list(sections_dir.glob("section_*.md")))


def get_scores_summary() -> dict | None:
    """Try to load latest scores from results.tsv."""
    tsv = WORKDIR / "results.tsv"
    if not tsv.exists():
        return None
    scores = {}
    for line in tsv.read_text().splitlines():
        parts = line.split("\t")
        if len(parts) >= 5:
            section = parts[2]
            try:
                score = float(parts[4])
                scores[section] = max(scores.get(section, 0), score)
            except ValueError:
                pass
    return scores


def check_prerequisites(phase: str) -> bool:
    """Run the prerequisite checker."""
    script = WORKDIR / "autoarticle" / "pipeline.py"
    result = run(["uv", "run", "python", str(script), "--phase", phase, "--strict"], cwd=WORKDIR)
    return result.returncode == 0


def load_state() -> dict:
    """Load current state."""
    state_file = WORKDIR / "state.json"
    if state_file.exists():
        return json.loads(state_file.read_text())
    return {"phase": "foundation", "iteration": 0, "revision_cycle": 0}


def save_state(state: dict) -> None:
    """Save state."""
    state_file = WORKDIR / "state.json"
    state_file.write_text(json.dumps(state, indent=2))


# ─── Phase runners ────────────────────────────────────────────────────────────


def phase_foundation() -> bool:
    heading("Phase 1: Foundation")

    # Check prerequisites
    cprint("  Checking prerequisites...", YELLOW)
    ok = check_prerequisites("foundation")
    if not ok:
        cprint("  Prerequisites not met. Run: uv run python autoarticle/pipeline.py --phase foundation", RED)
        return False

    # Run foundation scripts
    foundation_dir = WORKDIR / "autoarticle" / "foundation"

    steps = [
        ("Outline", ["autoarticle/foundation/gen_outline.py", "--seed", "seed.txt", "--output", "outline.md"]),
        ("Voice",   ["autoarticle/foundation/gen_voice.py",   "--seed", "seed.txt", "--output", "voice.md"]),
        ("Sources", ["autoarticle/foundation/gen_sources.py", "--outline", "outline.md", "--seed", "seed.txt", "--output", "sources.md"]),
        ("Claims",  ["autoarticle/foundation/gen_claims.py",   "--outline", "outline.md", "--output", "claims.json"]),
    ]

    all_ok = True
    for name, cmd in steps:
        cprint(f"  [{name}]", CYAN)
        if not run_python(cmd[0], cmd[1:], cwd=WORKDIR):
            all_ok = False
            cprint(f"  [{name}] FAILED — continuing anyway", RED)

    if all_ok:
        cprint("\n  Running foundation evaluation...", YELLOW)
        run_python("autoarticle/revision/evaluate.py", ["--phase", "foundation"], cwd=WORKDIR)

        # Update state
        state = load_state()
        state["phase"] = "foundation"
        state["foundation_done"] = True
        save_state(state)
        cprint("\n  Foundation complete.", GREEN)
    else:
        cprint("\n  Foundation had failures. Review above.", RED)

    return all_ok


def phase_draft() -> bool:
    heading("Phase 2: Draft")

    cprint("  Checking prerequisites...", YELLOW)
    ok = check_prerequisites("draft")
    if not ok:
        cprint("  Prerequisites not met.", RED)
        return False

    section_count = count_outline_sections()
    cprint(f"  Outline has {section_count} sections.", CYAN)

    # Create sections dir
    sections_dir = WORKDIR / "sections"
    sections_dir.mkdir(exist_ok=True)

    # Draft each section
    all_ok = True
    for i in range(1, section_count + 1):
        cprint(f"\n  [Section {i}/{section_count}]", CYAN)
        if not run_python(
            "autoarticle/drafting/gen_draft.py",
            [str(i), "--output", f"sections/section_{i:02d}.md"],
            cwd=WORKDIR,
        ):
            cprint(f"  Section {i} FAILED", RED)
            all_ok = False

    # Anti-slop scan
    cprint("\n  [Anti-slop scan]", CYAN)
    if sections_dir.exists():
        ok_scan = run_python("autoarticle/drafting/anti_slop.py", [str(sections_dir), "--mode", "scan"], cwd=WORKDIR)
        if ok_scan:
            cprint("  Running anti-slop rewrite on flagged files...", YELLOW)
            run_python("autoarticle/drafting/anti_slop.py", [str(sections_dir), "--mode", "rewrite"], cwd=WORKDIR)

    # Evaluate
    cprint("\n  [Evaluate draft]", CYAN)
    run_python("autoarticle/revision/evaluate.py", ["--phase", "full"], cwd=WORKDIR)

    state = load_state()
    state["phase"] = "draft"
    state["draft_done"] = True
    save_state(state)

    return all_ok


def phase_revision(max_cycles: int = 5) -> bool:
    heading("Phase 3: Revision")

    cprint("  Checking prerequisites...", YELLOW)
    ok = check_prerequisites("revision")
    if not ok:
        cprint("  Prerequisites not met.", RED)
        return False

    section_count = count_sections()
    cprint(f"  {section_count} sections to revise.\n", CYAN)

    state = load_state()
    cycle = state.get("revision_cycle", 0)
    prev_overall = None
    sections_backup = None  # for restore-on-degradation

    for cycle in range(1, max_cycles + 1):
        state["revision_cycle"] = cycle
        save_state(state)

        heading(f"Revision Cycle {cycle}/{MAX_REVISION_CYCLES}")

        # ---- Snapshot sections BEFORE revision (for restore-on-degradation) ----
        sections_backup = {}
        for sf in sorted((WORKDIR / "sections").glob("section_*.md")):
            sections_backup[sf.name] = sf.read_text()

        # ---- Evaluate: per-section + full article ----
        cprint("  [Evaluate — per-section]", CYAN)
        eval_ok = run_python(
            "autoarticle/revision/evaluate.py",
            ["--phase", "per-section", "--output", f"eval_logs/cycle_{cycle}.json"],
            cwd=WORKDIR,
        )

        eval_file = WORKDIR / "eval_logs" / f"cycle_{cycle}.json"
        eval_data = None
        if eval_file.exists():
            try:
                eval_data = json.loads(eval_file.read_text())
            except (json.JSONDecodeError, OSError):
                pass

        current_scores = None
        overall = None
        if eval_data:
            current_scores = eval_data.get("scores", {})
            overall = eval_data.get("overall")

        # Fallback: parse overall from stdout if file unavailable
        if not overall:
            import re
            stdout_text = eval_ok.stdout if hasattr(eval_ok, "stdout") else ""
            m = re.search(r"OVERALL\s+([0-9.]+)", stdout_text)
            if m:
                overall = float(m.group(1))

        if overall is not None:
            cprint(f"  Overall score: {overall}/10", CYAN)
        else:
            cprint("  Could not parse overall score.", YELLOW)

        # ---- Check for degradation ----
        if prev_overall is not None and overall is not None and overall < prev_overall:
            cprint(f"\n  Score dropped ({prev_overall} → {overall}). Restoring sections from pre-revision snapshot.", RED)
            for name, content in sections_backup.items():
                (WORKDIR / "sections" / name).write_text(content)
            cprint("  Sections restored. Stopping revision.", RED)
            break

        if prev_overall is not None and overall is not None and abs(overall - prev_overall) < 0.2:
            cprint(f"\n  Score plateau detected ({prev_overall} → {overall}). Stopping.", GREEN)
            break

        if overall is not None and overall >= 8.5:
            cprint(f"\n  Score {overall} >= 8.5 — good enough to proceed.", GREEN)
            break

        if cycle == max_cycles:
            cprint(f"\n  Max cycles ({max_cycles}) reached.", YELLOW)
            break

        # ---- Identify target section from per-section scores ----
        weakest_section_num = 1
        target_dimension = "clarity"
        if eval_data and "per_section" in eval_data:
            ps = eval_data["per_section"]
            if ps:
                # Target the section with the lowest overall score
                target = min(ps, key=lambda x: x.get("overall", 10))
                weakest_section_num = target.get("section", 1)
                target_dimension = target.get("weakest", "clarity")
                cprint(f"  Per-section: section {weakest_section_num} is weakest ({target.get('overall')}/10, dimension={target_dimension})", CYAN)
                for entry in ps:
                    cprint(f"    Section {entry['section']:>2}: {entry['overall']:>4}  weakest={entry['weakest']}", GREY)
        else:
            cprint(f"  No per-section data — targeting section 1", YELLOW)

        # ---- Adversarial edit pass (still useful for context) ----
        cprint("\n  [Adversarial edit]", CYAN)
        run_python("autoarticle/revision/adversarial_edit.py", ["all", "--target-pct", "15", "--output", "edit_logs/"], cwd=WORKDIR)

        # ---- Revise the weakest section with its specific weakest dimension ----
        cprint(f"\n  [Revise section {weakest_section_num} — targeting {target_dimension}]", CYAN)
        run_python(
            "autoarticle/revision/gen_revision.py",
            [str(weakest_section_num), "--auto", target_dimension],
            cwd=WORKDIR,
        )

        # Anti-slop recheck on revised section
        cprint(f"\n  [Recheck anti-slop on section {weakest_section_num}]", CYAN)
        section_file = WORKDIR / "sections" / f"section_{weakest_section_num:02d}.md"
        if section_file.exists():
            run_python("autoarticle/drafting/anti_slop.py", [str(section_file), "--mode", "rewrite"], cwd=WORKDIR)

        prev_overall = overall
        cprint(f"\n  Cycle {cycle} complete.", YELLOW)

    state["phase"] = "revision"
    state["revision_done"] = True
    save_state(state)
    cprint(f"\n  Revision complete after {cycle} cycle(s).", GREEN)
    return True


def phase_polish() -> bool:
    heading("Phase 4: Polish")

    cprint("  Checking prerequisites...", YELLOW)
    ok = check_prerequisites("polish")
    if not ok:
        cprint("  Prerequisites not met.", RED)
        return False

    # Final anti-slop scan
    sections_dir = WORKDIR / "sections"
    if sections_dir.exists():
        cprint("  [Final anti-slop scan]", CYAN)
        run_python("autoarticle/drafting/anti_slop.py", [str(sections_dir), "--mode", "rewrite"], cwd=WORKDIR)

    # Build bibliography if sources were used
    seed_file = WORKDIR / "seed.txt"
    include_sources = "none"
    if seed_file.exists():
        for line in seed_file.read_text().splitlines():
            if line.startswith("include_sources:"):
                include_sources = line.split(":", 1)[1].strip()

    if include_sources != "none":
        cprint("\n  [Build bibliography]", CYAN)
        run_python("autoarticle/polish/build_bibliography.py", ["--claims", "claims.json", "--output", "bibliography.md", "--style", "apa"], cwd=WORKDIR)

    # Assemble final article
    cprint("\n  [Assemble final article]", CYAN)
    run_python("autoarticle/polish/build_final.py", ["--no-llm", "--output", "final_article.md"], cwd=WORKDIR)

    # Move bibliography to end if it exists
    bib = WORKDIR / "bibliography.md"
    final = WORKDIR / "final_article.md"
    if bib.exists() and final.exists():
        content = final.read_text()
        if "## Bibliography" not in content and "# Bibliography" not in content:
            content += "\n\n" + bib.read_text()
            final.write_text(content)
            cprint("  Bibliography appended to final article.", GREEN)

    state = load_state()
    state["phase"] = "polish"
    state["done"] = True
    save_state(state)

    cprint("\n  Polish complete.", GREEN)
    cprint(f"  Output: {final.resolve()}", CYAN)
    return True


def print_summary() -> None:
    """Print pipeline run summary."""
    heading("Pipeline Summary")

    state = load_state()
    tsv = WORKDIR / "results.tsv"
    if tsv.exists():
        lines = tsv.read_text().strip().splitlines()
        cprint(f"  Evaluation rows: {len(lines)}", RESET)

    sections_done = count_sections()
    cprint(f"  Sections drafted: {sections_done}", RESET)

    final = WORKDIR / "final_article.md"
    if final.exists():
        size = final.stat().st_size
        cprint(f"  Final article: {final.resolve()} ({size} bytes)", GREEN)
    else:
        cprint(f"  Final article: not produced yet", YELLOW)

    eval_dir = WORKDIR / "eval_logs"
    if eval_dir.exists():
        cycles = len(list(eval_dir.glob("cycle_*.json")))
        cprint(f"  Revision cycles: {cycles}", RESET)

    cprint(f"\n  State: {json.dumps({k: v for k, v in state.items() if k != 'debts'}, indent=4)}", CYAN)


# ─── Main ─────────────────────────────────────────────────────────────────────


PHASES = {
    "foundation": phase_foundation,
    "draft": phase_draft,
    "revision": phase_revision,
    "polish": phase_polish,
}


def main():
    parser = argparse.ArgumentParser(
        description="AutoArticle pipeline orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_pipeline.py --check                 # Validate prerequisites
  python run_pipeline.py --phase foundation        # Run only foundation
  python run_pipeline.py --all                    # Run all phases
  python run_pipeline.py --continue               # Resume from saved state
  python run_pipeline.py --dry-run --all          # Show what would run
        """,
    )
    parser.add_argument("--phase", choices=list(PHASES.keys()))
    parser.add_argument("--all", action="store_true", help="Run all phases in order")
    parser.add_argument("--continue", dest="do_continue", action="store_true", help="Continue from saved state")
    parser.add_argument("--check", action="store_true", help="Check prerequisites only")
    parser.add_argument("--dry-run", action="store_true", help="Show commands without running")
    parser.add_argument("--max-cycles", type=int, default=3, help="Max revision cycles (default: 3)")
    args = parser.parse_args()

    max_cycles = args.max_cycles

    if args.dry_run:
        cprint("DRY RUN — no commands will be executed", YELLOW)

    if args.check:
        heading("Prerequisite Check")
        for phase in PHASES.keys():
            ok = check_prerequisites(phase)
            symbol = "✓" if ok else "✗"
            cprint(f"  [{symbol}] {phase}", GREEN if ok else RED)
        return

    if args.do_continue:
        state = load_state()
        phase_order = list(PHASES.keys())
        current = state.get("phase", "foundation")
        if current in phase_order:
            start_idx = phase_order.index(current)
            phases_to_run = phase_order[start_idx:]
        else:
            phases_to_run = phase_order
        cprint(f"Continuing from phase: {current}", CYAN)
        cprint(f"Will run: {' → '.join(phases_to_run)}", CYAN)
    elif args.phase:
        phases_to_run = [args.phase]
    elif args.all:
        phases_to_run = list(PHASES.keys())
    else:
        parser.print_help()
        cprint("\nSpecify --phase, --all, or --check", YELLOW)
        return

    if args.dry_run:
        for phase in phases_to_run:
            cprint(f"  [WOULD RUN] {phase}", CYAN)
        return

    heading(f"AutoArticle Pipeline — {WORKDIR}")

    for phase in phases_to_run:
        runner = PHASES[phase]
        if phase == "revision":
            ok = runner(max_cycles=max_cycles)
        else:
            ok = runner()
        if not ok and phase in ("foundation", "draft"):
            cprint(f"\n{phase.capitalize()} failed. Fix errors and re-run with --continue", RED)
            break

    print_summary()


if __name__ == "__main__":
    main()

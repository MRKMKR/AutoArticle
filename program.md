# AutoArticle

Autonomous article writing pipeline. The agent transforms a seed
specification into a polished article through structured phases,
guided by automated evaluation and anti-slop enforcement.

## Required Reading

Before ANY writing or evaluation, the agent must internalize:
- `refs/article_types.md` -- Type definitions and quality criteria
- `refs/evaluation_rubric.md` -- Scoring dimensions and thresholds
- `refs/anti_slop.md` -- Full reference on AI writing tells
- `WORKFLOW.md` -- Step-by-step workflow
- `PIPELINE.md` -- Technical pipeline specification

## The Article Layer Stack

```
  Layer 5:  voice.md          -- HOW we write (tone, style, vocabulary)
  Layer 4:  outline.md        -- WHAT we cover (sections + key claims)
  Layer 3:  sources.md        -- WHAT WE RELY ON (external verification)
  Layer 2:  claims.json       -- WHAT WE CLAIM (structured factual claims)
  Layer 1:  sections/*.md     -- THE ACTUAL PROSE (one file per section)
  Cross-cutting: seed.txt     -- PROJECT BRIEF (type, length, audience, seed bullets)
```

## Setup

1. **Tag the run**: Create branch `article/<slug>` from master.
2. **Read all layer files** for full context.
3. **Verify seed.txt** is complete (type, title, length, tone, audience, bullets, examples).
4. **Verify state.json** shows phase=foundation.
5. **Confirm and go**.

## Phase 1: Foundation (no prose yet)

LOOP until foundation_score > 7.0:
  1. Run `python evaluate.py --phase=foundation`
  2. Identify the weakest dimension from the eval output
  3. Expand or revise that document:
     - outline.md: section structure and key claims
     - sources.md: external verification needs
     - voice.md: tone and style calibration
     - claims.json: structured factual claims
  4. If adding claims to claims.json, note source hints
  5. git commit with description of what changed
  6. Re-evaluate
  7. If score improved -> keep. If worse -> git reset --hard HEAD~1, discard.
  8. Log to results.tsv

Foundation priorities (weighted by evaluation rubric):
  - Clarity: Is every section's purpose and key claim clear?
  - Technical accuracy: Are claims precise, not vague?
  - Source coverage: Are verifiable claims identified and marked?

Cross-layer consistency checks on every iteration:
  - Each outline section has at least one specific key_claim
  - Claims in claims.json map to outline sections
  - Voice calibration matches target audience
  - Examples (if provided) are analyzed for transferable patterns

Exit: When foundation_score > 7.0, update state.json phase to "drafting".

## Phase 2: First Draft (sequential section writing)

FOR each section in outline order:
  LOOP until section_score > 6.0 or attempts > 5:
    1. Load context:
       - seed.txt (full)
       - voice.md (full)
       - outline.md (full, this section's entry highlighted)
       - sources.md (full)
       - Previous section's last ~500 words (for continuity)
       - Next section's outline entry (for flow)
    2. gen_draft.py → sections/section_NN.md
    3. anti_slop.py sections/section_NN.md --rewrite
    4. Run `python evaluate.py --section=NN`
    5. Keep/discard based on score
    6. If writing reveals a claim gap, log a debt in state.json
    7. Extract new claims from draft → update claims.json
    8. Log to results.tsv
    9. git commit

Forward progress over perfection. A 6.0 section is good enough.
Phase 3 is for polish.

After all sections drafted:
  10. Run anti_slop.py across all sections (mechanical pass)
  11. Update state.json phase to "revision"

## Phase 3: Revision (multi-cycle refinement)

LOOP until plateau across 2 consecutive full cycles:

### Cycle A: Clarity
  1. evaluate.py --dimension=clarity --full
  2. Identify lowest-scoring sections
  3. gen_revision.py <section> --dimension=clarity
  4. Commit, re-evaluate

### Cycle B: Conciseness
  1. adversarial_edit.py all --target=15%
  2. Apply classified cuts per section
  3. evaluate.py --dimension=conciseness --full
  4. Commit, re-evaluate

### Cycle C: Technical Accuracy
  1. evaluate.py --dimension=technical --full
  2. Identify technically weak claims
  3. fact_check.py --all
  4. Flag unverifiable claims → source or soften
  5. gen_revision.py affected --dimension=technical
  6. Commit, re-evaluate

### Cycle D: Source Integrity
  1. fact_check.py --all
  2. For each uncited claim: add citation or mark [unverified]
  3. build_bibliography.py
  4. evaluate.py --dimension=sources --full
  5. Commit

### Cycle E: Anti-Slop Final
  1. anti_slop.py sections/ --full-rewrite
  2. evaluate.py --dimension=slop --full
  3. Commit

### Plateau Detection
After each full cycle (all 5 dimensions evaluated):
  - If all dimension scores within ±0.2 of previous cycle → plateau
  - If 2+ dimensions improved by >0.5 in this cycle → continue
  - If plateau: update state.json phase to "polish"

## Phase 4: Polish

  1. build_final.py → final_article.md
  2. build_bibliography.py → bibliography.md (if sources required)
  3. Run evaluate.py --full for final scores
  4. If final_score > 8.0 → ready. If not → return to Phase 3 targeted fix.
  5. Commit final state as "ready for review"

## Context Window Strategy

ALWAYS loaded:
  - seed.txt (full)
  - voice.md (full)
  - outline.md (full)
  - sources.md (full)
  - refs/anti_slop.md (full)

PER SECTION (~10-15k tokens):
  - Target section (full)
  - Adjacent sections (prev + next)
  - claims.json (relevant entries)

## Evaluation Dimensions

Foundation: clarity, technical, source_coverage

Section: clarity, conciseness, technical, slop

Full article: clarity, conciseness, technical, sources, tone, slop

## Rules

- **NEVER STOP** during a phase. Keep looping until exit gate is met.
- **Simpler is better**: Don't add complexity for marginal gains.
- **Forward progress over perfection**: A 6.0 section is good enough.
  Phase 3 is for polish.
- **Log everything**: Every experiment goes in results.tsv.
- **Different judge**: Evaluation model should differ from writing model
  when possible to avoid self-congratulation bias.
- **Source or soften**: Any claim that cannot be verified must either
  be sourced or rewritten as speculation/qualification.
- **Anti-slop is non-negotiable**: Tier 1 words are always rewritten.
  No exceptions in final output.
- **Specificity over abstraction**: "the ESP32 runs at 240MHz" not
  "the chip is fast." "LiveKit's Phoenix transport" not "modern protocols."
- **Define terms on first use**: Every technical term must be explained
  or clearly scoped for the target audience level.

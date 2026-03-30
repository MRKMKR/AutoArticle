# PIPELINE

Full technical specification for the AutoArticle pipeline.

---

## Overview

AutoArticle transforms a seed specification into a polished article through four phases:

```
Phase 0: Setup     → branch created, seed.txt validated
Phase 1: Foundation → outline.md, sources.md, voice.md, claims.json
Phase 2: Draft     → sections/*.md (one per outline section)
Phase 3: Revision  → revised sections (multi-cycle)
Phase 4: Polish    → final output (markdown, HTML, LaTeX)
```

---

## Master Branch (Framework)

The `master` branch is the reusable framework — never edited by the pipeline.

```
FRAMEWORK (reusable, never edited by the pipeline):
  README.md              -- project overview
  WORKFLOW.md            -- step-by-step human guide
  PIPELINE.md            -- this file (automation spec)
  program.md             -- agent instructions per phase
  refs/
    anti_slop.md         -- word-level AI tell detection
    article_types.md      -- type definitions and quality criteria
    evaluation_rubric.md -- scoring dimensions and thresholds
  autoarticle/           -- Core pipeline scripts
    foundation/           -- Phase 1 generators
    drafting/            -- Phase 2 generators
    revision/            -- Phase 3 scripts
    polish/              -- Phase 4 scripts
    utils/               -- shared utilities

CONFIG:
  .env.example           -- API key template
  pyproject.toml         -- Python dependencies (httpx, dotenv)
  .python-version
  .gitignore             -- Excludes: .env, *.log, __pycache__/, eval_logs/, edit_logs/, briefs/
```

---

## Per-Article Branch (Generated)

Everything below is created per article on its branch.

```
PER ARTICLE (on article/<slug> branch):
  seed.txt               -- article specification
  outline.md             -- section structure + key claims per section
  sources.md             -- identified sources, external references
  voice.md               -- tone guide, what to avoid, audience calibration
  claims.json             -- factual claims needing verification
  sections/
    intro.md
    section_01.md
    section_02.md
    ...
    conclusion.md
  state.json             -- {phase: "foundation", iteration: 0, debts: []}
  results.tsv            -- experiment log (every keep/discard, per-dimension scores)
  eval_logs/*.json       -- full evaluation results per section
  edit_logs/*.json       -- adversarial cuts, per section
  briefs/*.md            -- revision briefs (input to gen_revision.py)
```

---

## THE PIPELINE

### Phase 0: Setup

```
INPUT:  seed.txt (user-provided)
OUTPUT: branch created, .env configured, state.json initialized

1. git checkout -b article/<slug>
2. Verify .env has ANTHROPIC_API_KEY
3. Verify seed.txt is complete (type, title, length, tone, audience, bullets, examples)
4. Create state.json with phase="foundation", iteration=0, debts=[]
```

### Phase 1: Foundation

```
INPUT:  seed.txt
OUTPUT: outline.md, sources.md, voice.md, claims.json
EXIT:   foundation_score > 7.0

Loop:
  1. gen_outline.py      → outline.md (sections + key claims per section)
  2. gen_sources.py      → sources.md (claims needing external verification)
  3. gen_voice.py        → voice.md (tone guide from examples + seed bullets)
  4. gen_claims.py       → claims.json (structured factual claims)
  5. evaluate.py --phase=foundation
  6. If score improved → git commit. If worse → git reset --hard HEAD~1.
  7. Identify weakest dimension → target next iteration at it.
  8. Log to results.tsv

Exit: When foundation_score > 7.0, update state.json phase to "drafting".
```

### Phase 2: First Draft

```
INPUT:  all foundation docs
OUTPUT: sections/*.md (one file per outline section)
EXIT:   all sections > 6.0

For each section in outline order:
  1. Load context window:
     - voice.md (full)
     - outline.md (full)
     - seed.txt (full)
     - Previous section's last ~500 words (for continuity)
     - Next section's outline entry (for flow)
  2. gen_draft.py → sections/section_NN.md
  3. anti_slop.py sections/section_NN.md
  4. evaluate.py --section=NN
  5. If score > 6.0 → keep, commit. If < 6.0 → discard, retry (max 5).
  6. Extract new claim entries from draft → update claims.json
  7. Log to results.tsv

Post-draft:
  8. Run anti_slop.py across all sections (mechanical pass)
  9. Update state.json phase to "revision"
```

### Phase 3: Revision

Multiple cycles, each targeting a specific dimension.

```
CYCLE A: CLARITY
  1. evaluate.py --dimension=clarity --full
  2. Identify lowest-scoring sections
  3. gen_revision.py <section> --dimension=clarity
  4. Commit, re-evaluate

CYCLE B: CONCISENESS
  1. adversarial_edit.py all --target=10-20%
  2. Apply top cuts per section
  3. evaluate.py --dimension=conciseness --full
  4. Commit, re-evaluate

CYCLE C: TECHNICAL ACCURACY
  1. evaluate.py --dimension=technical --full
  2. Identify technically weak claims
  3. fact_check.py --all
  4. Flag unverifiable claims → either source or soften claim
  5. gen_revision.py affected --dimension=technical
  6. Commit, re-evaluate

CYCLE D: SOURCE INTEGRITY
  1. fact_check.py --all
  2. For each uncited claim: add citation or mark as [unverified]
  3. build_bibliography.py
  4. evaluate.py --dimension=sources --full
  5. Commit

CYCLE E: ANTI-SLOP FINAL PASS
  1. anti_slop.py sections/ --full-rewrite
  2. evaluate.py --dimension=slop --full
  3. Commit

EXIT: When scores plateau across 2 consecutive full evaluation cycles.
Update state.json phase to "polish".
```

### Phase 4: Polish

```
INPUT:  all revised sections
OUTPUT: final article (markdown, HTML, or LaTeX)

1. build_final.py → final_article.md
2. build_bibliography.py → bibliography.md (if sources required)
3. Run evaluate.py --full for final scores
4. If final_score > 8.0 → ready. If not → return to Phase 3 for targeted fix.
5. Commit final state
```

---

## Key Scripts

### Foundation

```
gen_outline.py
  input: seed.txt
  output: outline.md
  prompt: Generate section structure based on article type + seed bullets.
          Each section gets: title, key_claims (what this section must cover),
          target_length, transition_to_next.

gen_sources.py
  input: outline.md, seed.txt
  output: sources.md
  prompt: For each key_claim, identify what external verification is needed.
          Note: Do NOT fetch sources yet. Just identify what is needed.

gen_voice.py
  input: seed.txt (examples field), seed bullets
  output: voice.md
  prompt: Derive tone, style, vocabulary preferences from examples.
          Define what to avoid (from anti_slop.md tier lists).
          Calibrate for target audience.

gen_claims.py
  input: outline.md, seed.txt
  output: claims.json
  prompt: Extract every factual claim from outline key_claims.
          Each claim: {id, text, section, needs_verification: bool,
                       source_hint: string, verified: bool}
```

### Drafting

```
gen_draft.py
  input: voice.md, outline.md, section_number, previous_section_excerpt, next_section_outline
  output: sections/section_NN.md
  prompt: Write section following outline key_claims, respecting voice.md.
          Max 3 sentences per paragraph. Active voice preferred.
          Define any technical terms on first use.

anti_slop.py
  input: section.md (or sections/ directory)
  output: annotated report + rewritten section
  modes:
    --scan: Report only
    --rewrite: Replace flagged passages
    --full-rewrite: Full section rewrite enforcing anti_slop rules
```

### Revision

```
evaluate.py
  modes: --phase=foundation, --section=N, --full, --dimension=<dim>
  dimensions: clarity, conciseness, technical, sources, tone, slop
  output: per-dimension 0-10 scores + per-section breakdown + weakest points

adversarial_edit.py
  input: sections/*.md or section_NN.md
  output: edit_logs/sNN_cuts.json
  modes:
    --target=X% : aim to cut X% of words
    --classify : categorize cuts (OVER-EXPLAIN, REDUNDANT, WEAK_EVIDENCE, etc.)
  Each cut: {text, section, line, classification, severity}

fact_check.py
  input: claims.json, sources.md
  output: claims.json (updated verified field)
  modes:
    --claim=N : check specific claim
    --all : check all unverified claims
    --cite : attempt to add citation for claim

gen_revision.py
  input: section_NN.md, edit_logs/sNN_cuts.json (optional), dimension
  output: revised sections/section_NN.md
  prompt: Rewrite section addressing weakest dimension per evaluation.
          If cuts provided: apply cuts first, then expand on clarity/technical.
```

### Polish

```
build_final.py
  input: sections/*.md (in order), outline.md, voice.md
  output: final_article.md
  behavior: Assemble sections, add transitions if missing,
            apply final voice pass, add table of contents if long.

build_bibliography.py
  input: claims.json, sources.md
  output: bibliography.md
  format: citation style (configurable: apa, ieee, chicago)
```

---

## State Management

### state.json (per article, gitignored)
```json
{
  "phase": "foundation|drafting|revision|polish",
  "iteration": 0,
  "debts": [
    {"trigger": "s03: claim about X needs verification",
     "affected": ["claims.json", "sections/section_03.md"],
     "status": "pending|resolved"}
  ],
  "scores": {
    "foundation": null,
    "draft": {},
    "revision": {"cycle": 0, "clarity": null, "conciseness": null,
                 "technical": null, "sources": null, "slop": null}
  }
}
```

### results.tsv
```
date	phase	section	score	dimension	action	details
2026-03-30	foundation	all	6.2	clarity	retry	Outline too vague in s03
2026-03-30	foundation	all	7.4	clarity	keep	Improved after revision
...
```

---

## Evaluation Weighting

```
final_score = (
  clarity        * 0.25 +
  conciseness    * 0.15 +
  technical      * 0.25 +
  sources        * 0.20 +
  tone           * 0.10 +
  slop           * 0.05
)
```

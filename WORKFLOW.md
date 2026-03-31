# WORKFLOW

Step-by-step guide to running AutoArticle.

For the full technical pipeline specification, see [PIPELINE.md](PIPELINE.md).

---

## Quick Start

```bash
# 1. Setup
cd ~/AutoArticle
cp .env.example .env   # Add your Anthropic API key

# 2. Create an article branch
git checkout -b article/my-article-slug

# 3. Write your seed in seed.txt (see seed format below)
nano seed.txt

# 4. Run the full pipeline
uv run python run_pipeline.py --from-scratch
```

The pipeline will:
1. Build outline, sources, voice, and claims (Phase 1)
2. Draft all sections sequentially (Phase 2)
3. Revise through clarity/conciseness/technical/sources/anti-slop cycles (Phase 3)
4. Assemble and typeset (Phase 4)

---

## Seed Format

Create a `seed.txt` file in the article root:

```
type: project          # see refs/article_types.md for options
title: "Building a Desktop AI Companion"
target_length: medium   # short / medium / long / feature
include_sources: basic  # none / basic / deep
tone: casual           # casual / semiformal / formal
audience: intermediate # beginner / intermediate / expert / general

seed_bullets:
- The friction of starting from a blank page is the primary motivation
- Traditional article writing processes often begin with minimal structure
- The goal is to transform simple seed information into complete articles
- Core idea: writing as a stack of layer files feeding into section drafts
- The pipeline runs four phases: Foundation, Draft, Revision, Polish
- Anti-slop regex kills AI tells (delve, utilize, leverage, etc.)
- LLM judge scores six dimensions per section for consistent evaluation
- Raspberry Pi 5 implementation achieves ~$0.02/article cost efficiency
- The hardest part was developing an effective evaluation signal for quality
- Future: automated source discovery and LLM-based assembly for content

examples:
- https://example.com/good-technical-writeup
- "Another good example: article title or URL"
```

---

## Running Phases Individually

```bash
# Foundation only
uv run python run_pipeline.py --phase foundation

# Drafting only
uv run python run_pipeline.py --phase drafting

# Revision only (with max cycle limit)
uv run python run_pipeline.py --phase revision --max-cycles 5

# Export only
uv run python run_pipeline.py --phase export
```

---

## Manual Tools

### Evaluation
```bash
uv run python evaluate.py --phase=foundation   # Score planning docs
uv run python evaluate.py --section=1           # Score a section
uv run python evaluate.py --full                # Score the whole article
```

### Anti-Slop
```bash
uv run python anti_slop.py sections/intro.md   # Scan one section
uv run python anti_slop.py sections/           # Scan all sections
```

### Revision
```bash
uv run python adversarial_edit.py all          # Find cuts in all sections
uv run python fact_check.py                    # Verify claims against sources
uv run python gen_revision.py 1 briefs/s01.md  # Rewrite section from brief
```

### Fact-Checking
```bash
uv run python fact_check.py --claim 5          # Check specific claim
uv run python fact_check.py --all              # Check all claims
```

### Export
```bash
uv run python build_final.py                   # Assemble final article
uv run python build_bibliography.py            # Generate citations
```

---

## The Three Loops

```
INNER LOOP (agent, runs overnight):
  modify → evaluate → keep/discard → repeat

OUTER LOOP (you, when you check in):
  read results → steer program.md / evaluate.py / planning docs
  → let the agent run again

REVISION LOOP (automated):
  clarity → conciseness → technical → sources → anti-slop
  → stop when scores plateau across 2 consecutive cycles
```

You're not writing the article. You're programming the system that writes the article.

---

## Phase Exit Gates

| Phase | Gate |
|-------|------|
| Foundation | `foundation_score > 7.0` |
| Draft | all sections `> 6.0` |
| Revision | plateau across 2 consecutive cycles |
| Final | `final_score > 8.0` or manual approval |

---

## Article Structure Output

```
sections/
  intro.md         # Hook + what this article is about
  section_01.md    # First major section
  section_02.md    # Second major section
  ...
  conclusion.md    # Summary + takeaways
```

Each section is drafted, evaluated, and revised independently before assembly.

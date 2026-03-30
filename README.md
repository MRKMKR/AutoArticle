# AutoArticle

An autonomous pipeline for writing, revising, and publishing technical articles, blog posts, and journalistic content. From scattered thoughts to polished, source-checked, anti-slop-reviewed articles.

Based on [NousResearch/autonovel](https://github.com/NousResearch/autonovel) — adapted for articles instead of novels.

---

## Quick Start

```bash
# Clone and setup
git clone https://github.com/MRKMKR/AutoArticle.git && cd AutoArticle
cp .env.example .env    # Add your API keys

# Install dependencies
uv sync

# Create a new article branch
git checkout -b article/my-article-slug

# Run the full pipeline
uv run python run_pipeline.py --from-scratch
```

---

## The Pipeline

### Phase 1: Foundation
Build the outline, source list, voice guide, and claims tracker from a seed. Loop until `foundation_score > 7.0`.

### Phase 2: First Draft
Write sections sequentially. Evaluate each one. Keep if `score > 6.0`, retry if not. Forward progress over perfection.

### Phase 3: Revision
Adversarial editing → apply cuts → clarity/conciseness/technical/sources passes → generate briefs → rewrite. Plateau detection stops the loop.

### Phase 4: Polish
Assemble sections, build bibliography, typeset to target format.

See [PIPELINE.md](PIPELINE.md) for the full technical specification.

---

## Article Types

| Type | Purpose |
|---|---|
| Explainer | Make complex thing accessible |
| How-To / Tutorial | Enable reader to do something |
| Project Write-Up | What you built/learned |
| Opinion / Thought Leadership | Persuade of a position |
| Review | Evaluate something fairly |
| News / Reporting | Report on events accurately |
| Retrospective | Lessons from experience |
| Reference / Documentation | Technical specification |

See [refs/article_types.md](refs/article_types.md) for full type definitions.

---

## Tools

### Foundation
| Tool | Purpose |
|------|---------|
| `gen_outline.py` | Seed → structured outline |
| `gen_sources.py` | Identify claims needing verification |
| `gen_voice.py` | Tone guide from examples + seed |
| `gen_claims.py` | Extract factual claims needing verification |

### Drafting
| Tool | Purpose |
|------|---------|
| `gen_draft.py` | Write a single section |
| `anti_slop.py` | Banned word enforcement per section |

### Revision
| Tool | Purpose |
|------|---------|
| `evaluate.py` | Per-dimension scoring + slop detection |
| `adversarial_edit.py` | "Cut X words" analysis → classified cuts |
| `fact_check.py` | Verify claims against sources |
| `gen_revision.py` | Rewrite from revision brief |

### Polish
| Tool | Purpose |
|------|---------|
| `build_final.py` | Assemble sections → final output |
| `build_bibliography.py` | Generate citations if required |

---

## File Structure

```
FRAMEWORK (reusable, on master):
  program.md              — Agent instructions per phase
  refs/anti_slop.md       — Word-level AI tell detection
  refs/article_types.md   — Type definitions and quality criteria
  refs/evaluation_rubric.md — Scoring dimensions and thresholds
  PIPELINE.md             — Full automation specification
  WORKFLOW.md             — Step-by-step human guide

PER ARTICLE (on article/<slug> branch):
  seed.txt                — Article specification
  outline.md              — Section structure + key claims
  sources.md              — Identified sources and claims
  voice.md                — Tone guide, what to avoid
  claims.json             — Factual claims needing verification
  sections/               — Individual section drafts
  state.json              — Pipeline state tracker

CONFIG:
  .env.example            — API keys (Anthropic)
  pyproject.toml          — Python dependencies
```

---

## Two Immune Systems

1. **Mechanical** (`anti_slop.py`): regex scans for banned words, vague quantification, weasel phrases, claim inflation.

2. **LLM Judge** (`evaluate.py`, separate model): scores clarity, conciseness, technical accuracy, source integrity, tone consistency.

---

## API Keys

Only Anthropic is required for the core pipeline:

| Service | Key | Used for |
|---------|-----|---------|
| Anthropic | `ANTHROPIC_API_KEY` | Writing, evaluation (Sonnet + Opus) |

Copy `.env.example` to `.env` and add your key.

---

## Inspiration

- [NousResearch/autonovel](https://github.com/NousResearch/autonovel) — novel pipeline base
- [karpathy/autoresearch](https://github.com/karpathy/autoresearch) — autonomous research loop
- [aiming-lab/AutoResearchClaw](https://github.com/aiming-lab/AutoResearchClaw) — research paper pipeline
- [slop-forensics](https://github.com/sam-paech/slop-forensics) and [EQ-Bench Slop Score](https://eqbench.com/slop-score.html)

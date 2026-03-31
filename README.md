# AutoArticle

An autonomous pipeline for writing, revising, and publishing technical articles. From scattered thoughts to polished, source-checked, anti-slop-reviewed articles.

**Status:** Working end-to-end with ZAI (glm-4-plus) and Anthropic (Claude). Tested on ARM64 Linux (Raspberry Pi 5 / Pi).

---

## Quick Start

```bash
git clone https://github.com/MRKR/AutoArticle.git
cd AutoArticle

# Copy and edit environment
cp .env.example .env
# Add your API key to .env (see API Keys section below)

# Install dependencies
uv sync

# Create a working branch
git checkout -b article/my-article-slug

# Create your seed file (seed.txt) — see Seed Guide below
# Then run the full pipeline
uv run python run_pipeline.py --all

# Or resume from where you left off
uv run python run_pipeline.py --continue

# Run a specific phase
uv run python run_pipeline.py --phase foundation
uv run python run_pipeline.py --phase draft
uv run python run_pipeline.py --phase revision
uv run python run_pipeline.py --phase polish
```

---

## Seed File Format

Create `seed.txt` in the project root. This is the only input you provide — everything else is generated.

```yaml
type: project           # Article type (see Article Types below)
title: "My Article Title"
target_length: medium   # short | medium | long
include_sources: basic  # none | basic | full
tone: casual           # casual | semi-formal | formal
audience: intermediate # beginner | intermediate | expert
spelling_region: us    # us | gb — controls spelling enforcement (e.g. "organize" vs "organise")
revision_strength: gentle  # gentle | aggressive — how forcefully to apply cuts in revision cycles

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
```

### What Makes a Good Seed

**Good seeds:**
- Specific facts, real experiences, actual decisions made
- Named technologies, specific prices, real timelines
- Controversial or nuanced takes welcome
- Why this topic matters to you (or why it should matter to the reader)

**Bad seeds:**
- Vague goals ("explore the potential of AI")
- Generic statements anyone could write
- No named technologies or specifics
- Just a title with no bullets

### Example: Good vs Bad

**Bad seed (too vague):**
```
type: project
title: "Building with AI"
target_length: medium
seed_bullets:
- I used AI tools to build something
- It was interesting
- AI is changing software development
```

**Good seed (specific, experiential):**
```
type: project
title: "Building a Desktop AI Companion"
target_length: medium
tone: casual
audience: intermediate
seed_bullets:
- I built an ESP32-based AI companion with vision
- It uses LiveKit for voice and Hermes Agent for orchestration
- The hardware is cheap (~$30 SenseCAP Watcher)
- I went through several iterations (xiaozhi -> agentic -> current)
- The goal is proactive, on-device, privacy-first AI
- For neurodivergent people, AI could notice what you miss
- Current status: voice works, vision experimental, long-term memory functional
```

### Spelling Region

`spelling_region` controls which spelling conventions are enforced throughout the pipeline:

| Value | Effect |
|-------|--------|
| `us` (default) | US spellings enforced; British variants flagged as errors |
| `gb` | British spellings enforced; US variants flagged as errors |

When set, the anti-slop scanner detects regional spelling violations (e.g. "organize" vs "organise", "color" vs "colour", "behavior" vs "behaviour") and the rewrite pass corrects them. The LLM is instructed to use the correct regional spelling throughout.

### Revision Strength

`revision_strength` controls how aggressively revision cycles apply cuts and rewrites:

| Value | Effect |
|-------|--------|
| `gentle` (default) | Only high-severity cuts applied. Minimal text change — preserves original phrasing where adequate. Small, safe improvements only. Never produces a worse score. |
| `aggressive` | All cuts (high + medium) applied. Significant restructuring, filler removal, and rewrites. Higher risk of score regression but can produce substantially tighter output. |

Use `aggressive` when you want a tight final draft and are willing to accept score volatility during revision cycles. Use `gentle` for incremental, safe improvement across multiple runs.

---

## API Keys

AutoArticle supports two LLM providers. Set one in `.env`:

### ZAI / GLM (ZhipuAI) — Recommended (cheaper, good quality)

```env
AUTOARTICLE_PROVIDER=zai
GLM_API_KEY=your_zai_key_here
ZAI_BASE_URL=https://api.z.ai/api/paas/v4
AUTOARTICLE_WRITER_MODEL=glm-4-plus
AUTOARTICLE_JUDGE_MODEL=glm-4-plus
```

Get a key at https://model-platform.zhipuai.cn

### Anthropic (Claude)

```env
AUTOARTICLE_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-key-here
AUTOARTICLE_WRITER_MODEL=claude-sonnet-4-20250514
AUTOARTICLE_JUDGE_MODEL=claude-sonnet-4-20250514
```

---

## The Pipeline

### Phase 1: Foundation
Generates the structural layer files from your seed:
- `outline.md` — section structure with key claims
- `voice.md` — tone guide (what to write, what to avoid)
- `sources.md` — claims that need source verification
- `claims.json` — structured factual claims

### Phase 2: Draft
Writes each section of the article one at a time. Runs `anti_slop.py` after each section to remove AI tells. Then runs full evaluation.

### Phase 3: Revision
Multi-cycle revision loop with stable per-section scoring and automatic degradation recovery:
1. Evaluate each section individually (3 averaged judge calls for stability) — identifies the lowest-scoring section and its weakest dimension
2. Snapshot all sections before making changes
3. Adversarial edit pass — finds verbose or weak passages
4. Revise the lowest-scoring section, targeting its specific weakest dimension
5. Anti-slop recheck on revised section
6. If overall score dropped vs previous cycle — restore sections and stop
7. If score plateaus or improves sufficiently — continue (max 3 cycles)

### Phase 4: Polish
- Final anti-slop scan
- Build bibliography if `include_sources` is set (from `sources.md` / `claims.json`)
- LLM-based assembly: two-pass transition planner + voice-guided final assembly

---

## Article Types

| Type | Purpose | Notes |
|------|---------|-------|
| `project` | What you built and learned | Best for personal/hands-on topics |
| `explainer` | Make a complex topic accessible | Needs sources |
| `how-to` | Enable the reader to do something | Steps must be verifiable |
| `opinion` | Persuade of a position | Be explicit about your stance |
| `review` | Evaluate something fairly | Cover pros and cons |
| `retrospective` | Lessons from experience | Be honest about failures |
| `reference` | Technical specification | Prioritise precision |

For full criteria see `refs/article_types.md`.

---

## Two Immune Systems

**1. Mechanical (anti-slop.py)**
Regex scanner that kills banned AI words on sight: delve, utilize, leverage, facilitate, elucidate, testament, synergy, etc. Also catches vague quantification (many, several, rather) and flags passive voice.

**2. LLM Judge (evaluate.py)**
Scores six dimensions per section: clarity, conciseness, technical accuracy, source integrity, tone consistency, slop. Per-section scores identify the exact section to revise; the weakest dimension of that section drives targeted revision. Each evaluation averages 3 judge calls for stable signals — reduces per-call variance from ~1.5 points to ~0.5. Restore-on-degradation prevents compounding quality loss across cycles.

---

## Output Files

```
seed.txt              — Your input (never overwritten by pipeline)
outline.md            — Generated section structure
voice.md              — Generated tone guide
sources.md            — Generated source/claim list
claims.json           — Generated structured claims
sections/
  section_01.md       — One file per outline section
  ...
final_article.md      — Assembled article (pipeline output)
bibliography.md       — Citations (if include_sources != none)
eval_logs/
  cycle_N.json        — Per-cycle evaluation (per-section scores + overall)
edit_logs/
  section_NN_cuts.json — Per-section adversarial cut lists
state.json            — Pipeline state (which phase, cycle, etc.)
```

---

## Security

- API keys are in `.env` which is `.gitignore`'d
- Pre-commit hook scans all staged files for API keys before commit
- Keys are only loaded via `python-dotenv` from `.env` at runtime
- No keys are ever printed to stdout or logged
- `.env.example` contains only placeholder values (`***`) and comments

**Pre-commit hook installation:**
```bash
cp pre-commit-hook .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

---

## Recommended Workflow

```bash
# 1. Start from a clean master
git checkout master
git pull origin master

# 2. Create article branch
git checkout -b article/my-article-slug

# 3. Write seed.txt
vim seed.txt

# 4. Run the pipeline
uv run python run_pipeline.py --all

# 5. Review the output
cat final_article.md

# 6. If not happy with results:
#    - Edit individual section files in sections/
#    - Or re-run specific phases
#    - Or just edit final_article.md directly (it's yours)
```

---

## What's Missing

- **Fact-checking:** `claims.json` identifies which claims need verification, but the actual verification step (fetching URLs, checking facts against sources) is not yet automated. Set `include_sources: basic` or `full` in `seed.txt` to generate claims — verification is planned.

## Inspiration

- [NousResearch/autonovel](https://github.com/NousResearch/autonovel) — novel pipeline base
- [slop-forensics](https://github.com/sam-paech/slop-forensics) — banned word detection
- [EQ-Bench Slop Score](https://eqbench.com/slop-score.html) — slop measurement

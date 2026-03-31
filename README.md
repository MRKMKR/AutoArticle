# AutoArticle

An autonomous pipeline for writing, revising, and publishing technical articles. From scattered thoughts to polished, source-checked, anti-slop-reviewed articles.

**Status:** Working end-to-end with ZAI (glm-4-plus) and Anthropic (Claude). Tested on ARM64 Linux (Raspberry Pi 5 / Asgard-Pi).

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

seed_bullets:
- First concrete fact, observation, or claim about the topic
- Second point — specific details beat vague ideas every time
- Third point
- ... (6-15 bullets works well; 3 is too few, 20 is too many)
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
Multi-cycle revision loop:
1. Evaluate the full article (scores: clarity, conciseness, technical, sources, tone, slop)
2. Adversarial edit — finds verbose or weak passages
3. Revise the section with the most flagged cuts, targeting the weakest dimension
4. Anti-slop recheck on revised section
5. Repeat until score plateaus or max cycles (5) reached

### Phase 4: Polish
- Final anti-slop scan
- Build bibliography (from `sources.md`)
- Assemble all sections into `final_article.md`

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
A separate model call scores six dimensions: clarity, conciseness, technical accuracy, source integrity, tone consistency, slop. Returns per-section and overall scores. The revision loop targets the weakest dimension.

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
  cycle_N.json        — Per-cycle evaluation scores
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

## Inspiration

- [NousResearch/autonovel](https://github.com/NousResearch/autonovel) — novel pipeline base
- [slop-forensics](https://github.com/sam-paech/slop-forensics) — banned word detection
- [EQ-Bench Slop Score](https://eqbench.com/slop-score.html) — slop measurement

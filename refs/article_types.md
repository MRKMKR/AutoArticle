# Article Types

Each type has a different structure, purpose, and evidence requirements.

---

## Explainer

**Purpose:** Make a complex topic accessible to a general or semi-technical audience.

**Structure:**
- Hook (why should the reader care?)
- What is it? (plain-language definition)
- How does it work? (stepped explanation)
- Why does it matter? (real-world significance)
- Where is it going? (future outlook)

**Length:** Medium to Long (800-3000 words)
**Sources:** Yes — depth required. Link to primary sources, papers, official docs.
**Audience:** General to intermediate
**Tone:** Semiformal, accessible, patient with complexity

**Quality markers:**
- Jargon is either defined or avoided
- Analogies used to bridge complex concepts
- Reader emerges knowing more than they did

---

## How-To / Tutorial

**Purpose:** Enable the reader to accomplish a specific task.

**Structure:**
- Goal statement (what you'll build/do by the end)
- Prerequisites (what you need before starting)
- Step-by-step (numbered, clear, each step completable)
- Troubleshooting (common failure modes)
- Next steps (where to go after)

**Length:** Any — completeness matters more than length
**Sources:** Optional — rely on official docs
**Audience:** Depends on the topic
**Tone:** Clear, direct, instructional. Second person ("you").

**Quality markers:**
- Steps are independently verifiable
- No step assumes knowledge from a future step
- Error cases are addressed before they occur

---

## Project Write-Up

**Purpose:** Share what you built, how you built it, and what you learned.

**Structure:**
- What it is + why you built it (motivation)
- The approach (architecture, key decisions)
- What went well (wins worth sharing)
- What was hard (honest struggles)
- What you'd do differently (lessons)
- Links / code (if applicable)

**Length:** Medium (500-2000 words)
**Sources:** Optional — project-specific
**Audience:** Peers (other builders)
**Tone:** Casual to semiformal. Honest. First person.

**Quality markers:**
- Specific over general ("I used a queue" not "I used good architecture")
- Decisions are justified with reasoning, not just outcome
- Failure is documented as learning, not just failure

---

## Opinion / Thought Leadership

**Purpose:** Persuade the reader of a specific position.

**Structure:**
- The claim (what you believe, stated clearly)
- The reasoning (why you believe it)
- Evidence (examples, data, experience)
- Counterarguments (addressed honestly)
- The takeaway (what follows from your position)

**Length:** Medium (600-2000 words)
**Sources:** Citations required for factual claims
**Audience:** Intermediate to expert
**Tone:** Semiformal. Confident but not dismissive of alternatives.

**Quality markers:**
- Position is stated clearly, not buried
- Counterarguments addressed, not dismissed
- Evidence distinguishes between "I think" and "here's proof"

---

## Review

**Purpose:** Evaluate something fairly — strengths, weaknesses, for whom.

**Structure:**
- What it is (concise — reader should already know)
- What it does well (honest positives)
- Where it falls short (honest negatives)
- Who it's for (and who should avoid it)
- The verdict (buy/skip/conditional)

**Length:** Medium (500-2000 words)
**Sources:** Yes — compare against stated claims
**Audience:** General to intermediate
**Tone:** Fair, balanced, specific.

**Quality markers:**
- Strengths and weaknesses are specific, not generic
- Comparison is against同类而非不同类
- Recommendation is actionable and honest

---

## News / Reporting

**Purpose:** Report accurately on events or developments.

**Structure:**
- What happened (lead — most important first)
- Who was involved
- When and where
- Why it matters (context)
- What comes next

**Length:** Short to Medium (<500-1500 words)
**Sources:** Primary — first-hand accounts, official statements, documents
**Audience:** General
**Tone:** Formal-neutral. Facts, not opinions.

**Quality markers:**
- Attribution on every claim
- Distinguishes between confirmed facts and unconfirmed reports
- Context provided without editorializing

---

## Retrospective

**Purpose:** Reflect on experience and extract lessons.

**Structure:**
- Setting the scene (context)
- What happened (the story)
- What I learned (insights, hard-won)
- What I'd tell my past self (advice)
- Where it left me (outro)

**Length:** Medium (600-2000 words)
**Sources:** Optional — experiential
**Audience:** Peers, or your future self
**Tone:** Personal, honest. First person.

**Quality markers:**
- Specific moments, not vague abstractions
- Lessons are grounded in concrete events
- Honest about difficulty without dwelling

---

## Reference / Documentation

**Purpose:** Provide authoritative technical specification.

**Structure:**
- Overview (what this is, scope)
- Specification (numbered items, tables)
- Examples (annotated)
- Edge cases (if applicable)
- Changelog (if versioned)

**Length:** Any — completeness and accuracy are paramount
**Sources:** Official specs, standards documents
**Audience:** Expert
**Tone:** Formal. Precise. No opinions.

**Quality markers:**
- Every statement is accurate or explicitly marked as opinion
- Examples are runnable/copy-pasteable
- Edge cases are not glossed over

---

## Type Detection Heuristics

When the seed type is unclear, look at the seed bullets:

| Signal | Likely Type |
|---|---|
| "how do I...", "I want to build..." | How-To |
| "I built...", "I made..." | Project Write-Up |
| "X is confusing because...", "I don't understand..." | Explainer |
| "I think X should...", "X is wrong because..." | Opinion |
| "should I use X or Y?", "is X worth it?" | Review |
| "what happened with X", "X just announced..." | News |
| "looking back...", "lessons from..." | Retrospective |
| "the spec for X", "how X works technically" | Reference |

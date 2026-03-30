# Anti-Slop Reference

A field guide to AI-generated writing patterns, adapted for technical articles and blog posts.

"Slop" = text that reads like unedited LLM output. Low information density, predictable structure, vocabulary no human would naturally use.

---

## Tier 1 — Kill on Sight

These almost never appear in natural writing. Rewrite the sentence.

| Slop word | Use instead |
|---|---|
| delve | dig into, explore, examine |
| utilize | use |
| leverage (verb) | use, apply, take advantage of |
| facilitate | help, enable, make possible |
| elucidate | explain, clarify |
| embark | start, begin |
| endeavor | try, attempt |
| encompass | include, cover |
| multifaceted | complex, varied |
| tapestry | (delete — describe the actual thing) |
| testament (as in "a testament to") | shows, proves, demonstrates |
| paradigm | model, approach, framework |
| synergy | (delete the sentence) |
| holistic | whole, complete, full-picture |
| catalyze | trigger, cause, spark |
| juxtapose | compare, contrast |
| nuanced (as filler) | (cut — show the nuance instead) |
| realm | area, field, domain |
| landscape (metaphorical) | field, space, situation |
| myriad | many |
| plethora | many, a lot |

---

## Tier 2 — Suspicious in Clusters

Fine in isolation. Three in one section = rewrite.

| Slop word | Use instead |
|---|---|
| robust | strong, solid, reliable |
| comprehensive | complete, thorough |
| seamless / seamlessly | smooth, clean, without friction |
| cutting-edge | new, latest, modern |
| innovative | new, original, clever |
| streamline | simplify, speed up |
| empower | let, help, give the ability |
| foster | encourage, grow, support |
| enhance | improve, boost |
| elevate | raise, improve |
| optimize | improve, tune |
| scalable | grows with you |
| pivotal | important, key, central |
| intricate | complex, detailed |
| profound | deep, significant |
| resonate | connect with, hit home |
| underscore | highlight, stress, show |
| harness | use, put to work |
| navigate (metaphorical) | deal with, work through, handle |
| cultivate | build, grow, develop |
| bolster | strengthen, support |
| galvanize | motivate, push |
| cornerstone | foundation, basis, core |
| game-changer | (be specific) |
| transformative | (be specific about what changed) |

---

## Tier 3 — Filler Phrases

Delete the phrase. State the thing directly.

| Phrase | Replace with |
|---|---|
| "It's worth noting that..." | State the thing directly |
| "It's important to note that..." | State the thing directly |
| "In conclusion..." | End the piece — no announcement needed |
| "To summarize..." | End the piece — no announcement needed |
| "The fact of the matter is..." | State the matter |
| "It goes without saying..." | Say it |
| "Needless to say..." | Say it |
| "As previously stated..." | Don't repeat — build on it |
| "At the end of the day..." | Cut — what point are you stalling? |

---

## Article-Specific Flags

### Claim Inflation
These words inflate claims beyond what evidence supports. Use sparingly and honestly.

| Phrase | Problem |
|---|---|
| revolutionary | Overused. What specifically changed? |
| groundbreaking | Overused. What specifically is new? |
| game-changing | What actually changed? |
| disruptive | Often vague. What disrupted what? |
| revolutionary | What specifically was revolutionized? |

### Vague Quantification
Be specific. "Many" means nothing without a number or context.

| Vague | Better |
|---|---|
| many | specific number or "most" |
| several | specific number |
| significantly | specific magnitude |
| quite | specific degree |
| rather | specific degree |
| a lot | specific number |

### Weasel Words
These hedge claims that should be stated directly.

| Weasel | Problem |
|---|---|
| "it is believed that" | Who believes? Cite them. |
| "research suggests that" | What research? Cite it. |
| "it is thought that" | By whom? |
| "experts say" | Which experts? |
| "studies show" | Which studies? |
| "evidence points to" | What evidence? |

### Passive Voice (overuse)
Passive is fine in moderation. Flag when >15% of sentences are passive.

Passive example: "It was decided that..."
Better: "We decided that..."

---

## Anti-Slop Workflow

1. Run anti_slop scanner after each draft pass
2. Tier 1 words → automatic rewrite
3. Tier 2 clusters → review, rewrite if unnatural
4. Tier 3 phrases → delete + rephrase
5. Article-specific flags → verify claims can support the language

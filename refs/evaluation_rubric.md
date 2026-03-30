# Evaluation Rubric

Scoring dimensions used to evaluate article quality at each phase.

---

## Dimensions

### Clarity (0-10)

Does the reader understand every sentence on the first read?

- 9-10: Accessible to target audience without effort
- 7-8: Mostly clear, minor rereading needed
- 5-6: Some passages need rereading
- 3-4: Frequent confusion points
- 1-2: Incomprehensible in places
- 0: Unreadable

**Scored per section, then averaged.**

### Conciseness (0-10)

Could any section lose 20% of words without losing meaning?

- 9-10: No fat whatsoever
- 7-8: A few words could trim
- 5-6: 10-20% could cut
- 3-4: 20-40% could cut
- 1-2: Verbose throughout
- 0: Each sentence has obvious bloat

### Technical Accuracy (0-10)

Are technical claims correct and precisely stated?

- 9-10: All claims accurate, precise language
- 7-8: Minor imprecision in wording, no factual errors
- 5-6: One or two claims need qualification
- 3-4: Several claims are misleading or wrong
- 1-2: Significant factual problems
- 0: Fundamental errors throughout

### Source Integrity (0-10)

Are claims backed by cited sources? Are citations legitimate?

- 9-10: All claims cited, all citations verifiable
- 7-8: All major claims cited, minor gaps
- 5-6: Some claims lack citation, or some citations weak
- 3-4: Several unsupported claims as fact
- 1-2: Most claims lack support
- 0: No sources or all sources fabricated/unreachable

### Tone Consistency (0-10)

Does the piece maintain its target tone throughout?

- 9-10: Tone consistent and appropriate throughout
- 7-8: Minor drift in 1-2 sections
- 5-6: Noticeable inconsistency in places
- 3-4: Frequent shifting between tones
- 1-2: Whiplash between casual and formal
- 0: No coherent tone

### Slop Score (0-10, inverted)

How much does this read like unedited LLM output?

- 9-10: Natural human voice, no tells
- 7-8: Mostly natural, occasional filler
- 5-6: Several suspicious passages
- 3-4: Frequent slop patterns
- 1-2: Obvious LLM output throughout
- 0: Indistinguishable from bulk AI generation

---

## Phase Exit Gates

### Phase 1 — Foundation
| Dimension | Threshold |
|---|---|
| Clarity (outline) | > 7.0 |
| Technical Accuracy (outline) | > 7.0 |
| Source Integrity (claims) | > 6.5 |

### Phase 2 — Draft
| Dimension | Threshold |
|---|---|
| Clarity | > 6.0 per section |
| Technical Accuracy | > 6.0 |
| Slop Score | > 5.0 |

### Phase 3 — Revision
Cycle exit requires all dimensions > 7.0, or plateau across 2 consecutive cycles.

---

## Scoring Workflow

1. Run `evaluate.py --phase=<phase> --article=<slug>` 
2. Review per-dimension scores
3. Identify lowest dimension
4. Target next iteration at weakest dimension
5. Log scores to `results.tsv`

---

## Weighted Average (Final Score)

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

Sources and technical accuracy are weighted highest — core article quality. Clarity next. Tone and slop are important but can be corrected in polish.

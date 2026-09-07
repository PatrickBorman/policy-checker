# External-source test — 7 September 2026

The corpus in `policies/` was written by the author of the checker. This test removes that: verbatim passages
from four documents nobody here wrote (`sources/`), an LLM extracts the variables and rules (`policy_checker/extract.py`),
the normal pipeline translates, checks and repairs. No hand-written reference encodings. Six policy sets.

| source | policy set | verdict | on inspection |
|---|---|---|---|
| Greenblatt et al. 2023, *AI Control* | trusted monitoring + defer to trusted | realisable | — |
| Greenblatt et al. 2023 | untrusted monitoring + honeypots | realisable | the excerpt does not mention budget exhaustion, so the honeypot-after-budget gap found in the hand-written version cannot appear |
| Greenblatt et al. 2023 | trusted editing | unrealisable | **artefact**: "top 2%" and "top 20%" extracted as independent booleans; the repair returned is exactly the missing domain fact, `G(!(top_2 & !top_20))` |
| Bhatt et al. 2025, *Ctrl-Z* | defer to resample | unrealisable | **artefact, induced by the extraction prompt**: audit and resample-more were made mutually exclusive in one step; the paper's procedure is sequential. Repair search degraded: 60 s, 316 candidates, a 10-assumption repair |
| Claude Code docs, *Configure permissions* | rule evaluation for one call | unrealisable | **artefact**: the EndConversation exception is stated as taking precedence over deny/ask rules; extraction kept "deny → block" absolute. Repair returned the exception |
| OpenAI Agents SDK docs, *Guardrails* | input/output guardrails | unrealisable | **artefact**: "input guardrails run only for the first agent" is a scoping statement; extraction turned it into an obligation on the controller. Repair returned the correct reading, `G(!(!is_first_agent & input_tripwire))` |

## What this shows

**Zero genuine conflicts in the external sources.** All four unrealisable verdicts are modelling artefacts
introduced at the prose-to-rules step: dropped subset relations between thresholds, dropped precedence, a scope
statement read as an obligation, and one exclusivity the extraction prompt pushed for. The rules-to-verdict half
of the pipeline behaved exactly as on the hand-written corpus; the prose-to-rules half is where trust breaks.

Two things redeem it, partially:
- In three of four cases the repair engine returned *precisely the fact the extraction lost*. A reader can dismiss
  each false positive in seconds, and the repair is a usable prompt for fixing the model. That is a real property
  of the method - it tells you what assumption your formalisation is missing - but it is not conflict detection.
- The two protocols that came out realisable are the two whose excerpts are complete enough to formalise
  without extra facts.

## Consequences for the claims

- "Half of realistic policy sets have a conflict" (RESULTS.md) is a statement about the hand-written corpus and
  should be read that way. On external text the pipeline's positives were artefacts.
- The reliable unit is a *rule set with declared variables*, not prose. The honest product boundary is: humans
  (or a much more careful extractor) produce the variables and rules; the checker takes it from there.
- Extraction needs, at minimum: explicit domain constraints between derived booleans (subset relations between
  thresholds), explicit precedence extraction, and a distinction between scope statements (environment
  assumptions) and obligations (guarantees). None of that is hard; all of it was missing here.
- The repair engine's search degrades with more independent environment variables (Ctrl-Z case). Weakest-repair
  selection and a better interpolant would both help.

Raw data: `policies_external/*.yaml`, `out_ext/`, `sources/`.

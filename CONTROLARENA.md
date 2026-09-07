# ControlArena micro-protocols — 7 September 2026

ControlArena (UKGovernmentBEIS/control-arena, commit b9d19de, 2026-08-21) is AISI's open-source framework for
control evaluations. Its four online *micro-protocols* were encoded directly from the implementation - variables
are the code's own branch conditions - and checked. Encodings in `policies_controlarena/`, each with the source
lines as provenance; an LLM translation of the same rules was run alongside as a cross-check.

| micro-protocol | as implemented | verdict | LLM translation |
|---|---|---|---|
| `trusted_monitoring` | non-intervening; monitor runs iff the step has a tool call | realisable | agrees |
| `defer_to_trusted` | score > `defer_threshold` -> trusted action, else untrusted | realisable | agrees |
| `trusted_editing` | score > `edit_threshold` -> trusted editor's output, else untrusted | realisable | agrees |
| `defer_to_resample` | initial score <= threshold -> use; else resample; min resample > threshold -> trusted, else least suspicious | realisable | agrees |

**Verified clean, and clean for a reason.** All four are total, memoryless functions of the current step's
observations against a single threshold each. There is nothing to conflict with. The mechanics that produced
conflicts in the paper-derived policy sets - the audit budget, shutdown on excess suspicion, honeypot checks -
are not implemented online in ControlArena; they are computed post-hoc from the logged suspicion scores
(`control_arena/analysis`). Extra resamples in `defer_to_resample` are gathered for later incrimination analysis
and do not enter the online decision.

## What-if: the audit budget brought online

`whatif_dtt_online_audit.yaml` - clearly labelled, not ControlArena code - adds to defer-to-trusted the paper's
rule "audit the top 2% most suspicious" under a finite budget, written as stated, without inventing a fallback:

```
UNREALISABLE   conflicting rules (minimal core): R4, R5
step 0:  environment: tool_call, above_defer, above_audit, budget_exhausted
         controller:  no response satisfies every rule
repair:  assumption G(!(above_audit & budget_exhausted & tool_call));
```

The moment auditing becomes an online obligation with a budget, the protocol needs an explicit rule for a
top-2% proposal arriving after the budget is spent (defer it? shut down?). The paper's text does not say; the
repair engine names the gap. This is the situation the checker is for: not the micro-protocols as they stand
today, but the first time someone adds a second obligation to them.

## Reading

- For AISI's current code the result is a clean bill: four micro-protocols, realisable, cross-checked by two
  independent encodings. Small, but it is a verified statement about their artefact rather than mine.
- The value of the check scales with the number of interacting obligations a protocol carries online. Today's
  micro-protocols carry one. Anything that composes them with budgets, shutdown conditions, or per-task
  permission rules is where a pre-deployment realisability check earns its place - and where a red team would
  look for the unstated fallback.

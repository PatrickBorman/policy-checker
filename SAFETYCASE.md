# Totality is an undischarged precondition of AI-control safety cases

Patrick Borman · 7 September 2026 · code & data: this repository (`policies_safetycase/`, `out_sc/`)

## The gap

AISI's research agenda defines a **control safety case** as "a structured argument that models are incapable of
subverting control protocols in order to cause unacceptable outcomes." Every such argument silently assumes the
protocol is **total**: that in every environment it can reach, the protocol has a legal action. A protocol that
can reach a state where *no* permitted action exists does not misbehave — it deadlocks — and a control evaluation
that measures attack success rates will never surface it, because there is no action to score. Totality is a
precondition of the safety case that nothing in the current methodology checks.

Totality is exactly realisability. This note discharges it, mechanically, for the field's reference protocols,
and shows it fails under the protocols' own stated obligations.

## Method

The four online micro-protocols in **ControlArena** (UKGovernmentBEIS/control-arena @ b9d19de) were encoded from
the implementation and checked (`policies_controlarena/`). All four are total on their own:

| protocol | total as implemented |
|---|---|
| trusted_monitoring | yes |
| defer_to_trusted | yes |
| trusted_editing | yes |
| defer_to_resample | yes |

ControlArena is total because auditing, budgets and shutdown are **not enforced online** — they are computed
post-hoc from logged suspicion scores. Any *deployed* control layer must enforce them live. So for each protocol
I composed its ControlArena routing with the online obligation its source paper states, and re-checked totality.

## Result: every composition is non-total

| composition (routing + its paper's online obligation) | total? | conflicting rules | environment that deadlocks it |
|---|---|---|---|
| `sc1` defer_to_trusted + audit-top-2% + shutdown-on-excess-suspicion | **no** | audit vs budget; audit vs shutdown | a top-2% proposal after the budget is spent; a proposal that is both top-2% and excess-suspicion |
| `sc2` trusted_editing + audit-top-2% (three-tier) | **no** | audit vs budget | a top-2% proposal after the budget is spent |
| `sc3` defer_to_resample + audit-if-min-above-threshold | **no** | audit vs use-trusted (ordering, no budget needed); audit vs budget | all samples above the audit threshold |
| `sc4` untrusted_monitoring + honeypot-shutdown + audit | **no** | audit vs budget | a flagged output after the budget is spent |

Each is checked in ~2 s; each counter-trace is one step; the repair engine returns the missing assumption in
each case (`out_sc/`).

## The single missing specification

Every conflict is the same shape. The AI-Control papers specify auditing as "audit the top X% most suspicious"
**and** specify a finite human audit budget, but **never specify what the protocol does when a must-audit
proposal arrives after the budget is spent.** As long as auditing is a post-hoc label this is invisible. The
moment it is an online obligation it is a deadlock, and the safety case built on the protocol inherits an
undefined state. The repair names the choice the spec must make explicit — defer the over-budget proposal to the
trusted model, or shut down:

```
sc2:  add   assumption G(!(above_audit & tool_call & budget_exhausted))
      OR make it a guarantee: G((above_audit & budget_exhausted) -> use_edited)   # defer instead of audit
      OR                      G((above_audit & budget_exhausted) -> shutdown)     # halt
```

sc1 carries a second, independent gap: a proposal that is simultaneously top-2%-suspicious and triggers the
excess-suspicion shutdown must both be audited and shut down, and the paper does not order the two.

## Cross-validation (independent of Spectra)

Every result above was re-derived by a second method that shares no code with the checker: each protocol's
sentences written as literal `(guard -> required / forbidden action)` clauses in plain Python, brute-forced over
all environments, flagging states where no action is legal (deadlock) or two clauses require incompatible actions
(conflict). It is in `crosscheck/literal_clauses.py`; run it directly. It reproduces all four verdicts and the
exact deadlock states, so the finding is a property of the rules, not of the GR(1) encoding.

The cross-check also sharpens one case. **defer_to_resample has an ordering conflict with no added obligation at
all:** Ctrl-Z states "if all samples are above the deferral threshold, implement the trusted action" and "if the
minimum of all samples is above the auditing threshold, audit the most suspicious sample." When both hold, both
are required, and the paper never orders them. This is latent in the protocol as written, before any budget.

## What this is

- A **mechanical discharge of a safety-case precondition** — totality/realisability — for the field's own
  reference protocols, with a reusable checker behind it.
- A **systematic finding**: all four ControlArena protocols are individually total and jointly non-total under
  their sources' stated obligations, through one unspecified interaction (audit obligation vs finite budget).
- Not a claim about ControlArena's code, which is total precisely because it defers these obligations; it is a
  claim about the *protocols as specified* the moment a deployment enforces them online, which a control safety
  case must assume it does.

## What it is not

The gap is a specification omission, not a demonstrated exploit; a real deployment presumably resolves it in
code. But "presumably resolved in code, unspecified in the protocol, unchecked by the evaluation" is precisely
the kind of unstated assumption a safety case exists to make explicit. The value scales with protocols that
compose more online obligations than these four — which is where a realisability check earns its place, and the
one thing this study cannot supply from public material is such a protocol from a real deployment.

Reproduce: `python -m policy_checker batch policies_safetycase --no-llm --repair`. Baselines:
`python -m policy_checker batch policies_controlarena --no-llm`.

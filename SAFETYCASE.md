# The audit-budget boundary in AI-control safety cases

Patrick Borman · code & data: this repository (`policies_controlarena/`, `policies_safetycase/`, `policies_probe/`, `crosscheck/`)

## Claim

A control protocol carries two claims a safety case relies on: **safety** (a suspicious action is never executed
unchecked) and **usefulness** (real work still gets done). Both are computed assuming auditing is available
whenever the protocol calls for it. Under a *finite, online* audit budget the two claims collide, and at
exhaustion the protocol must do something its specification never states — execute what it promised to audit
(safety claim broken) or refuse it (usefulness claim broken, and burning the budget becomes a denial-of-service).
The reported figures describe a protocol that isn't the one running after exhaustion. This note makes that
precise and checks it mechanically on the field's reference protocols.

It is a **specification-level** observation, not a bug in anyone's code. It comes in two strengths, and I am
explicit below about which parts need a reactive-synthesis engine and which a SAT solver would settle.

## Setup

ControlArena's four online micro-protocols (UKGovernmentBEIS/control-arena @ b9d19de) were encoded from the
implementation (`policies_controlarena/`). As implemented, all four are total — there is always a legal action —
**because auditing, budgets and shutdown are computed post-hoc from logged suspicion scores, not enforced
online.** A deployed control layer has to enforce them live. So for each protocol I composed its routing with the
online obligation its *source paper* states (audit the top X%, shut down on excess suspicion, honeypots) under a
finite audit budget, and re-checked. The added obligations are from the papers, not from ControlArena's code —
the code sidesteps the issue precisely by keeping them post-hoc.

## Result 1 — the static conflict (single-state; a SAT solver suffices)

Every composition reaches a state with no legal action, and in each case the minimal conflict is one pair of
rules:

| composition | conflicting rules | the state |
|---|---|---|
| `sc2` trusted_editing + audit-top-2% | audit must fire vs budget forbids it | top-2% arrives, budget spent |
| `sc1` defer_to_trusted + audit + shutdown | audit vs budget; and audit vs shutdown | as above; plus top-2% *and* excess-suspicion at once, which the paper never orders |
| `sc3` defer_to_resample + audit | audit vs implement-trusted (an ordering gap **with no budget at all**) | all samples above threshold |
| `sc4` untrusted_monitoring + honeypot + audit | audit vs budget | flagged output, budget spent |

**Honest calibration:** these are **single-state contradictions**. I re-derived every one with an independent
brute-force checker that shares no code with the formal engine and only ever inspects one state at a time
(`crosscheck/literal_clauses.py`) — it reproduces them all. That is the proof they are single-state: a one-step
check finds them, so the reactive machinery is not doing the work here. A SAT solver, or a loop over 2ⁿ
conditions, is the right tool for this layer. The `defer_to_resample` ordering gap is the sharpest, because it is
latent in the protocol *as written*, before any budget is added.

## Result 2 — the dynamic conflict (genuinely needs a reactive/liveness check)

The static conflict is also arguably *fail-safe*: a protocol with no legal move doesn't let the untrusted model
act. Give the controller an always-available "hold/block" action and the unrealisability disappears — it is
simply forced into **fail-closed** once the budget is spent (`policies_probe/sc2_abstain.yaml`, realisable). So
the deadlock is an artefact of forcing "audit specifically"; the real content is what the forced totalisation
costs. Stated as a liveness question, that content is engine-necessary:

- **Safety** (`G (sus -> !execute)`) plus **usefulness** (`GF (execute)`, progress infinitely often), against an
  adversary who can keep producing suspicious actions, is **unrealisable** (`policies_probe/live_free.yaml`).
- Add one assumption — suspicion is not permanent (`GF (!sus)`) — and it becomes **realisable**
  (`policies_probe/live_fair.yaml`).

Same guarantees; realisability flips on an infinite-horizon fairness assumption. A single-state check can't see
this (safety holds in every individual state), and neither can bounded reachability (the failure is "progress
*infinitely often*"). This is the one place the GR(1) engine earns its keep — and it maps directly onto the
safety-vs-usefulness tradeoff the field already optimises: no shield guarantees both against an adversary who can
suspiciously-jam forever; you only get both by *assuming* the adversary relents, i.e. that audit capacity is
never exhausted — the assumption a real deployment can't enforce.

**Where it stops:** a *quantitative* version (audit cost vs replenishment rate) is **not** a GR(1) result — its
justice operator (`GF`, "infinitely often") is too coarse to make rates matter, and I confirmed the threshold
collapses to "does the budget ever replenish," which is inspectable (`policies_probe/res_norepl.yaml` unrealisable
vs `res_repl.yaml` realisable). A genuinely non-inspectable resource threshold needs energy/mean-payoff games — a
different, heavier formalism than this engine, flagged here rather than claimed.

## The one missing specification

Across all of it, the omission is the same: the AI-Control papers specify "audit the top X%" **and** a finite
audit budget, but never what the protocol does when a must-audit case arrives after the budget is spent. The tool
surfaces the choice rather than making it — the repair it returns is an *assumption* (`G !(above_audit &
budget_exhausted & tool_call)`), i.e. "assume this never happens," which is not a fix but the decision a human
must take on purpose: defer the over-budget case, hold it (fail-closed), or shut down. Each is a different,
unpriced safety/usefulness tradeoff, and the reported numbers assume none of them.

## What this is, and is not

- **Is:** a precise account of an unstated assumption a control safety case relies on (unbounded / always-available
  audit), demonstrated on the field's own reference protocols, cross-validated two independent ways, with the one
  genuinely reactive case isolated from the many single-state ones.
- **Is not:** a bug in ControlArena's code (which defers the obligations), nor a demonstrated exploit. The static
  gaps are single-state and want a SAT check, not this engine; the engine is justified only on the liveness case.
  The value grows with protocols that compose more online obligations and carry state over time — which is exactly
  what public material does not yet provide, and the reason the interesting test is a real deployed control stack.

Reproduce: `python -m policy_checker batch policies_controlarena --no-llm` (baselines, all total);
`python -m policy_checker batch policies_safetycase --no-llm --repair` (compositions);
the probes in `policies_probe/` via `policy_checker.check`; and `python crosscheck/literal_clauses.py`.

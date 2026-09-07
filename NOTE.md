# Checking agent control policies before deployment: realisability, counter-traces, and repairs

Patrick Borman · September 2026 · code and data: `policy-checker` repository

## Claim

Control measures for AI agents — monitors, permission systems, escalation and audit rules — are rule sets.
Rule sets written by several people for several threat models accumulate contradictions, and current practice
finds them at runtime, when a monitor fires or an agent freezes. This note reports a pipeline that finds them
before deployment, in seconds, and explains each one as a short run the environment can force.

The check is *realisability*, not model checking: does a control strategy exist that satisfies every rule
whatever the agent and the world do? The distinction matters because the agent under control is adversarial.
When no strategy exists, an interpolation-based engine (from my MSc thesis) proposes the weakest environment
assumption that restores one. Read the other way round, that assumption is the failure condition — the
situation an attacker needs to create for the control layer to have no legal move.

## Example

Four rules for an email-sending support agent: every proposed send is resolved as allow, block or escalate
(G1); never allow without user confirmation in the same step (G2); never escalate twice in a row (G3); never
block while a refund case is open (G4).

```
UNREALISABLE   conflicting rules (minimal core): G1, G2, G3, G4
step 0:  environment: req_send, refund_open   [not: user_confirm]
         controller:  escalate
step 1:  environment: req_send, refund_open   [not: user_confirm]
         controller:  no response satisfies every rule:
             (nothing)  violates G1      block  violates G4
             allow      violates G2      escalate  violates G3
repair:  assumption G(!(req_send & !user_confirm & refund_open));
```

Two unconfirmed send proposals during an open refund and the controller is out of moves. The repair says
exactly when the policy set is safe — and therefore exactly what an adversarial agent would do.

## Method

1. Rules in English, with declared environment variables (what the agent/world does) and system variables
   (the controller's decisions), are translated to GR(1) in the Spectra language by an LLM with structured
   output and a static validator (undeclared variables, `next()` of a system variable in an assumption).
2. Spectra decides realisability (polynomial for GR(1)), extracts a minimal unrealisable core, and a
   minimised counter-strategy; a small evaluator attributes each losing controller response to the rule it
   violates.
3. The refinement engine computes a counter-trace, a Craig interpolant over the trace, and a candidate
   assumption; it backtracks over traces until realisability is restored.

## Results (23 policy sets, 108 rules; 7 September 2026)

Policy sets modelled on published control protocols (trusted monitoring, trusted editing, untrusted
monitoring with honeypots, defer-to-resample, incident response) and on product and regulatory policies
(IDE-agent permissions, DLP for browsing agents, pre-trade controls, content moderation, AI-Act-style human
oversight, clinical triage, hiring). Each rule has a hand-written encoding as reference.

| | |
|---|---|
| unrealisable sets | 12 / 23 |
| cores minimal and complete under single-rule deletion | 12 / 12 |
| repairs found; valid on fresh re-solve; non-vacuous | 12 / 12 / 12 |
| LLM translation, fresh full pass, weakest models: same verdict as reference | 23 / 23 (21 identical cores) |
| time per set: translate / check / repair | 5.6 s / 1.2 s / 2.1 s |

Conflicts I did not write in: the honeypot protocol has no legal move once the audit budget is spent (a
honeypot can be neither shipped nor audited); the vehicle rules never say whether an operator stop or a low
battery wins; defer-to-resample is unrealisable without the trusted-model availability assumption it never
states — and the engine recovers precisely that assumption.

One translation failure mode was found and fixed: a positive obligation ("when the kill switch is on, every
call is denied") encoded without its trigger, `G (kill_switch -> deny)`, forces a decision in steps with
nothing to decide and manufactures a conflict. One sentence in the prompt removed it.

## Limitations

The corpus author built the checker; sets were written faithfully to their sources, not to conflict, but they
are mine. The fragment is booleans with one step of memory — no counters, budgets or timers, which real
protocols need (Spectra supports bounded integers; the repair step does not yet). The repair returned is the
first found, not provably the weakest; the interpolator is a BDD stand-in for MathSAT.

## Ask

One real control-policy set, written by the people who deploy it, in whatever form they write it. The result
becomes meaningful the day this finds a conflict in a protocol its authors believed was fine.

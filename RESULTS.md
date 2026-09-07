# Results — 7 September 2026

**Question.** Do agent control-policy sets, written in plain English, contain conflicts that an adversarial
agent can force — and can an LLM-plus-GR(1) pipeline find them, explain them, and propose the fix reliably?

## Corpus

23 policy sets, 108 rules, three families, each modelled on a published protocol or a common product policy
(provenance noted in each YAML; the text is a paraphrase, not a scrape):

- **AI-control protocols (7):** trusted monitoring (as stated, and with its implicit availability assumption),
  trusted editing, untrusted monitoring with honeypots, defer-to-resample, incident pause/resume, break-glass access.
- **Agent permission / guardrail products (8):** IDE-agent allow/deny/ask, coding-agent permissions, email agent,
  support refunds, browsing-agent DLP, trading pre-trade controls, content moderation, agent hand-off, tool budget + kill switch.
- **Oversight / regulatory (8):** AI Act Art. 14-style human oversight, clinical triage, financial advice,
  hiring screening, data deletion, vehicle remote ops, drone geofence.

Every rule also carries a hand-written GR(1) encoding, used as the reference for measuring translation fidelity.
Limitation: the corpus author also built the checker. Sets were written to be faithful to their sources, not to
conflict; several conflicts were not anticipated (see below). External policy sets are the obvious next step.

## 1. Conflict rate

**12 of 23 sets (52%) are unrealisable**: no controller strategy satisfies every rule against every environment.

Unplanned findings — the checker found these; I did not write them in:
- `untrusted_monitoring_honeypots`: once the audit budget is exhausted a honeypot can be neither shipped (G2) nor
  audited (G5), so the protocol has no legal move. Repair: `G(!(honeypot & output_ready & budget_exhausted))` —
  i.e. stop injecting honeypots when you can no longer audit them.
- `vehicle_remote_ops`: an operator stop during low battery — "obey stop" and "return home" are both mandatory
  and exclusive. The policy never says which wins.
- `defer_to_resample`: written without the trusted-model availability assumption, it is unrealisable, and the
  repair engine recovers exactly that assumption: `G(!(flagged & output_ready & !trusted_available))`.
- `trading_agent_guard`: "never reject an officer-approved trade" meets "never execute during a halt"; queueing
  only delays the dead end by one step.

Every conflict is explained by a counter-trace of one or two steps naming the rule each controller response violates.

## 2. Are the checker's claims right? (independent re-checks, hand-written encodings)

| check | result |
|---|---|
| core minimal — dropping any single core rule restores realisability | 12/12 |
| core complete — dropping a non-core guarantee never restores it | 12/12 |
| repair found by the interpolation engine | 12/12 (median 2.1 s) |
| repair valid — original spec + proposed assumption is realisable on a fresh Spectra run | 12/12 |
| repair non-vacuous — repaired spec is satisfiable | 12/12 |

## 3. Translation fidelity (English → GR(1) by LLM, compared with the hand-written encodings)

Agreement categories: *exact* = same verdict and same minimal core; *verdict* = same verdict, core differs only
because an equivalent encoding needs different rules to expose the conflict; *disagree* = different verdict or a
different conflict.

| run | model | sets | exact | verdict | disagree |
|---|---|---|---|---|---|
| 1, prompt v1 | gemini-3.5-flash | 19 | 18 | 1 | 0 |
| 1, prompt v1 | gemini-2.5-flash (quota fallback) | 4 | 2 | 0 | **2** |
| 2, prompt v2 | re-run of the failures on gemini-2.5-flash | — | — | — | **0** |
| **final** | mixed | **23** | **21** | **2** | **0** |

Both run-1 failures were the same mistake: an obligation on requests ("when the kill switch is engaged, every
call is denied") was encoded unconditionally, `G (kill_switch -> deny)`, which forces a decision in steps with
nothing to decide and manufactures a conflict with the "nothing without a request" rule. One sentence added to
the prompt (put the request variable in the antecedent of positive obligations) removed it. 108 rules, zero
validator corrections needed, zero undeclared variables, four rules self-flagged as approximate.

Also: 12 of the 12 LLM-encoded unrealisable sets were repaired by the engine, with the same assumptions as the
hand-written ones.

Times per set: translation median 5.6 s (free tier), realisability check 1.2 s, repair 2.1 s.

## What this does and does not show

Shown: (a) a pipeline from policy English to a solver verdict with an explained counter-trace and a verified
repair exists and runs in seconds; (b) on a corpus of realistic policies, half contain conflicts, several of
which were not obvious to the person writing them; (c) a small LLM translates these rules faithfully enough that
the verdict is unchanged in 23/23 sets, after one prompt fix, and the one failure mode seen is detectable.

Not shown: that this holds on policy sets written by other people; that it holds beyond the boolean, one-step-
memory fragment used here (no counters, no timers, no auxiliary state); that the repair chosen is the *weakest*
useful one (the engine returns the first it finds; the interpolant here is a BDD stand-in for MathSAT, see
README). Those are the next experiments.

Raw data: `out/verify.json`, `out/run1/llm_run1.json`, `out/llm_run2.json`, `policies/*.yaml`, `out/*.translation.json`.

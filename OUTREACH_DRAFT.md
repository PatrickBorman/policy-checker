# Draft outreach — AISI Control team (Eric Winsor / Xander Davies)

First send; same people your EOI reaches. Send once you can say it in your own words and the repo link works.
Leads with the safety-vs-usefulness realisability tension (the defensible, in-their-currency framing), states
the limitation, and stays a question. Read as yourself and cut anything that isn't how you'd say it.

---

**Subject:** Do control safety cases assume an adversary-fairness condition they can't enforce?

Hi Eric / Xander,

I submitted an EOI for the agentic controls work; here's the substance behind it and a question I'd value
your read on.

A control protocol carries two claims: safety (suspicious actions don't get executed) and usefulness (real
work still gets done). Usefulness is a liveness property, and under a finite audit budget it collides with
safety in a specific way. I checked it as a reactive-synthesis (realisability) question rather than
empirically:

- "Never execute a suspicious action" + "make progress infinitely often", against an adversary who can keep
  producing suspicious-looking actions, is UNREALISABLE — no shield achieves both.
- Add one assumption — that suspicion isn't permanent (infinitely often a clean action arrives) — and it
  becomes realisable.

So a protocol's safety and usefulness numbers are both computed under an implicit assumption that the adversary
eventually relents (equivalently, that audit capacity isn't exhausted) — which a real deployment can't enforce.
At exhaustion the protocol has to silently pick fail-open (execute unaudited: safety claim breaks) or
fail-closed (refuse: usefulness claim breaks, and burning the budget becomes a denial-of-service). Either way
the reported figures describe a protocol that isn't the one running after exhaustion.

Repo, runs from a clean clone: https://github.com/PatrickBorman/policy-checker (SAFETYCASE.md is a page).

Being upfront about scope, because you'd raise it:
- This is a specification/realisability observation, not a bug in ControlArena's code — the code keeps auditing
  post-hoc, which sidesteps it. I encoded the routing logic of the micro-protocols, not the models or sandbox.
- The qualitative result above genuinely needs reactive synthesis (a one-step or reachability check can't see
  it — safety holds in every individual state). A *quantitative* threshold (audit cost vs replenish rate) does
  NOT — GR(1)'s "infinitely often" is too coarse; that would need energy games, which I flag as out of scope
  rather than claim. And most simpler policy conflicts I found are single-state, where a SAT check suffices.

My question: does a control safety case price what happens at audit-budget exhaustion — i.e. does it discharge
the adversary-fairness / unbounded-audit assumption, or treat the totalisation as an implementation default? If
it's the latter, the thing worth building is the quantified version: a protocol's safety/usefulness under
fail-open vs fail-closed, in your own evaluation setup. I'd value knowing whether that's a real gap before I
invest in it.

Best,
Patrick

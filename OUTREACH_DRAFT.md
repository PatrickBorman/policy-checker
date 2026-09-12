# Draft outreach — AISI Control team (Eric Winsor / Xander Davies)

First send. Same people your EOI reaches. Send once you can say it in your own words and the repo link works.
This version leads with the unpriced-totalisation framing (the defensible one), preempts the fail-safe
objection, and stays a question. Read it as yourself and cut anything that isn't how you'd say it.

---

**Subject:** Do control safety cases price what happens when the audit budget runs out?

Hi Eric / Xander,

I submitted an EOI for the agentic controls work; here's the substance behind it, and a question I'd
genuinely value your read on.

A control protocol's reported safety and usefulness are computed assuming auditing is available whenever the
protocol calls for it — in ControlArena the auditing/budget is handled post-hoc from logged scores. Under a
finite *online* budget, once it's exhausted the protocol has to do something its specification never defines:
either execute an action it promised to audit (fail-open — the safety number no longer holds) or refuse it
(fail-closed — the usefulness number no longer holds). Either way the reported figures describe a protocol
that isn't the one running after exhaustion. The totalisation-at-exhaustion looks like a safety-relevant policy
choice that the safety case doesn't price.

I found this by encoding ControlArena's micro-protocols and composing each with the online audit obligation its
source paper states; as GR(1) specs they become unrealisable at exhaustion. But I want to be upfront about two
things, because you'd raise them immediately:

- The bare "no legal move" is arguably fail-safe — a stuck protocol doesn't let the untrusted model act. The
  point isn't the deadlock; it's that a real system resolves it silently (usually toward availability), and
  that resolution is unexamined and unpriced. When I give the controller an explicit "hold/block" action the
  unrealisability disappears and it's simply forced fail-closed — which is the same point in a cleaner form.
- This is a specification-level observation, not a bug in your code — the code sidesteps it by keeping auditing
  post-hoc. It's the same shape as a documentation/spec consistency finding, and I'd frame it that way, not as
  an exploit.

(Encoding detail for the record: with budget as a free flag the conflict is single-state; with budget as a
decrementing counter it's genuinely reactive — the environment has to force enough must-audit cases to drain it
first — so the temporal version is real, not an artefact.)

Repo, runs from a clean clone: https://github.com/PatrickBorman/policy-checker (SAFETYCASE.md is a page).

My question: is "what the protocol does once the audit budget is exhausted" something you already price into a
control safety case, or is it treated as an implementation default? If the latter, the thing I'd want to build
is the quantified version — a protocol's safety/usefulness under fail-open vs fail-closed totalisation, in your
own evaluation setup — and I'd value knowing whether that's a real gap or already handled before I invest in it.

Best,
Patrick

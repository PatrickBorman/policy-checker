# Draft outreach — Redwood Research (Ryan Greenblatt / Buck Shlegeris)

Redwood co-created ControlArena and originated AI control, so the finding is about their own protocols — this
version is framed as "a gap in the protocols you defined", not "a gap in a methodology". Send only after you can
explain it in your own words (EXPLAINER.md). One recipient.

---

**Subject:** A totality gap in the ControlArena protocols (audit obligation vs finite budget)

Hi [name],

I revisited my MSc work — GR(1) specification repair, supervised by Dalal Alrajeh at Imperial — and pointed it
at the control protocols you formalised, and found something small but concrete.

A protocol is only well-defined if it has a legal action in every situation it can reach. That's a realisability
question, so it's mechanically checkable, and a control evaluation can't surface a violation of it, because a
protocol with no legal action deadlocks rather than misbehaves and scores no attack success.

I encoded ControlArena's four online micro-protocols and checked them. As implemented they're total — and they're
total precisely because auditing, budgets and shutdown are computed post-hoc from logged scores rather than
enforced online. Compose each protocol with the online obligation its source paper states — audit the top X%,
shut down on excess suspicion, honeypot checks — under a finite audit budget, and all four become non-total, each
with a one-step witness and the assumption that repairs it. The shared gap: the papers specify "audit the top X%"
and a finite human budget, but never what the protocol does when a must-audit case arrives after the budget is
spent. defer-to-resample has an ordering conflict (audit vs implement-trusted) even before any budget, purely as
written. I verified all of it a second, independent way that shares no code with the formal checker.

Repo, runs from a clean clone: https://github.com/PatrickBorman/policy-checker — the finding is SAFETYCASE.md,
one page; EXPLAINER.md is the plain-English version.

The honest limit is the reason I'm writing: these are public protocols, simple enough that the gap is a
specification omission a real implementation probably patches silently. The interesting case is a control stack
that composes several online obligations — where a genuine unintended deadlock would live — and that's exactly
what I can't get at from outside. If any of this is useful, or wrong in a way you'd want to tell me, I'd value a
short exchange. (I'm also in AISI's process for the control work; this is the substance behind it.)

Best,
Patrick

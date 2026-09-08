# Draft outreach — Control team (Eric Winsor / Xander Davies), or the Control Red Team recruiter

Not to be sent until: (1) repo pushed to GitHub and the link works from a clean clone; (2) you've read it in
your own voice and cut anything that isn't yours. Keep it short — this is a door-opener, not the paper.

---

**Subject:** Totality as an unchecked precondition in control safety cases — a small finding on ControlArena

Hi [name],

I revisited my MSc work (GR(1) specification repair, supervised by Dalal Alrajeh at Imperial) and pointed it at
AI control, and found something small but concrete I thought the Control team might want.

A control safety case assumes the protocol is *total* — that it has a legal action in every environment it can
reach. Nothing in the current methodology checks that, and a control evaluation can't surface a violation,
because a protocol with no legal action deadlocks rather than misbehaves, and scores no attack success. Totality
is just realisability, so it's mechanically checkable.

I encoded ControlArena's four online micro-protocols and checked them: all four are total as implemented. They're
total because auditing, budgets and shutdown are computed post-hoc rather than enforced online. When I compose
each protocol with the online obligation its own source paper states (audit the top X%, shut down on excess
suspicion, honeypot checks) under a finite audit budget — which a live deployment must enforce — all four become
non-total, each in about two seconds, each with a one-step counter-trace and the assumption that repairs it. The
common gap: the papers specify "audit the top X%" and a finite budget but never say what happens when a must-audit
proposal arrives after the budget is spent. defer-to-resample has an ordering conflict even before any budget.
It's cross-validated by an independent brute-force checker that shares no code with the formal one.

Repo (runs from a clean clone): [link]. The write-up is SAFETYCASE.md; the finding is a page.

The honest limitation is the reason I'm writing: this is a specification-level result on public protocols, which
are either too simple to conflict or resolve the gap silently in code. The one thing I can't do from outside is
run it on a real control stack — a protocol composing several online obligations, the kind that would actually
have a gap its authors didn't intend. If that's of any interest, I'd value even a short conversation.

I'm applying to the Control Red Team role / I've submitted an EOI for the agentic controls work; this is the
substance behind it either way.

Best,
Patrick

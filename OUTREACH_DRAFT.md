# Draft outreach — AISI Control team (Eric Winsor / Xander Davies)

First send. Same people your EOI reaches, so this is the substance behind it. Send only once you can
explain it in your own words (EXPLAINER.md) and after the repo link works. Read once as yourself and cut
anything that isn't how you'd say it.

---

**Subject:** A consistency check for control protocols — small finding on ControlArena, and a question

Hi Eric / Xander,

I submitted an EOI for the agentic controls work; this is the substance behind it, and a genuine question
I'd value your read on.

Control protocols are rule sets, and a rule set can reach a state where every action is forbidden by some
rule — the protocol has no legal move. That's an internal-consistency property (a realisability check), and
it's separate from the empirical safety/usefulness question: a protocol can be perfectly good against attacks
and still have a reachable state it deadlocks in, which an attack-success evaluation won't surface because a
stuck protocol scores nothing.

I encoded ControlArena's four online micro-protocols and checked them. As implemented they're consistent —
and that's because auditing, budgets and shutdown are computed post-hoc, not enforced online. Compose each
with the online obligation its source paper states, under a finite audit budget (what a live deployment must
do), and all four hit a state with no legal move — the shared gap being "audit the top X%" plus "the budget
is finite" with nothing specified for a must-audit case after the budget is spent. Repo, runs from a clean
clone: https://github.com/PatrickBorman/policy-checker (one-page write-up: SAFETYCASE.md).

Now the honest part, because you'll see it immediately. Most of these are single-state contradictions — the
rules are jointly unsatisfiable in one reachable state — not the harder reactive case where an adversary
forces a corner over time. On toy protocols the check is close to trivial; the reactive machinery only earns
its keep on protocols that carry state over time (budgets that deplete, counters, rate limits), and I can't
demonstrate that on public material because the public protocols are too simple. I also note the closest
formal work (Griffin/Thomson/Shlegeris/Abate, Games for AI Control) assumes protocols are well-defined rather
than checking it.

So my question is direct: is protocol-level consistency something you already treat as trivially handled in
practice, or is it a real unchecked precondition of a control safety case worth a tool? I'd rather know than
guess — and if it's the latter, the thing I'd want is a more realistic, stateful protocol to point it at.

Best,
Patrick

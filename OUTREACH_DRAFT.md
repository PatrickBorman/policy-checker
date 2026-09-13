# Email to send — AISI Control team (Eric Winsor / Xander Davies)

Ready to send. Repo link is in. Frames the consistency work as a precursor and signals the real interest:
applying formal verification as a real-time controller (shielding). Read once as yourself before sending.

TO: (see routing note at bottom)
SUBJECT: Precursor to a real-time control shield — a realisability question on ControlArena

---

Hi Eric / Xander,

I've submitted an EOI for the agentic controls work; this is the substance behind it, and where I'd like to
take it.

As a first probe I treated control protocols as rule sets and checked them for realisability — whether a
controller can satisfy every rule against an adversarial environment, or whether some reachable situation
leaves no legal move. Encoding ControlArena's micro-protocols and composing each with the online audit
obligation its source paper states (audit the top X%, under a finite budget), the interesting case is the
collision between safety ("never execute a suspicious action") and usefulness ("make progress infinitely
often"): against an adversary who can keep producing suspicious actions it's unrealisable, and it only becomes
realisable if you assume suspicion isn't permanent — an adversary-fairness condition a real deployment can't
enforce. At exhaustion the protocol has to silently pick fail-open (safety breaks) or fail-closed (usefulness
breaks; burning the budget becomes a DoS), and the reported numbers assume neither.

Repo, runs from a clean clone: https://github.com/PatrickBorman/policy-checker (SAFETYCASE.md is a page).

I want to be straight about scope: the offline consistency part is a precursor, not the hard problem — most of
what it catches is single-state and a SAT check would do; the reactive engine only earns its place on the
safety-vs-usefulness liveness case above. It's a specification-level observation, not a bug in your code.

Where I actually want to go is the real-time version: formal verification as an online controller / shield that
sits in the agent loop and blocks unsafe actions, with the offline realisability check as its precondition (a
shield exists only if the spec is realisable). The open problems that interest me are the ones that make it
hard in practice — grounding the abstract predicates in real tool-calls, getting the adversary model right, and
the quantitative/budgeted cases that fall outside GR(1). My MSc was on GR(1) specification repair, so this is
the direction I'm trying to build toward.

My question: is real-time shielding / runtime enforcement something the Control team sees as a live direction,
and is protocol-level realisability a precondition you'd want checked — or is it treated as hygiene today? I'd
value your read before I invest further, and I'd welcome a short conversation.

Best,
Patrick

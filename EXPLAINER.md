# What this actually is — in plain words

A primer to read before talking to anyone about it. No maths. If you can say the things in
"How to explain it in one minute" out loud, you're ready.

## The problem, in one sentence

When you give an AI agent a set of rules about what it may and may not do, those rules can quietly
contradict each other — and nobody currently checks for that before the agent is running.

## Why that matters

Control rules for agents pile up: "never send an email without confirmation", "always escalate after two
failures", "audit anything suspicious", "shut down if things look wrong". Different people write them, for
different worries, and they accumulate. Sometimes, in some particular situation, two rules demand opposite
things, or every allowed action is forbidden by some rule. When that happens the agent doesn't misbehave —
it gets *stuck*, because there's no legal move. Today that's only discovered when it happens live.

## What "check" means here (the one idea to get)

There are two different questions you can ask about a rule set:
- "Can this specific system go wrong?" — that's what most tools do (run it, or model-check it).
- "Does *any* valid way to follow all the rules exist, no matter what the agent and the world do?" — that's
  the question this asks. In formal-methods language it's called **realisability**. If the answer is no,
  the rules are internally impossible to satisfy — there's a situation with no legal action.

The second question is the useful one for control rules, because the agent is adversarial: it will find the
gap between two rules on purpose. You want to know the gap exists *before* you deploy, not after.

## What I built

A pipeline: you write the rules in plain English; a language model turns them into a precise logical form;
an engine (the core of my MSc thesis) checks whether they're jointly satisfiable; and if they're not, it
does two things — shows a short worked example of a situation where the agent is stuck, and proposes the
smallest change to the rules that fixes it. The checking engine is 20-year-old formal-methods machinery
(GR(1) synthesis); my thesis contribution was making the "why is it broken / how to fix it" part fast.

## What I found (the result worth mentioning)

AI-safety researchers have published "control protocols" — standard recipes for supervising an untrusted
AI (monitor its output, audit the suspicious 2%, defer to a trusted model, shut down if things look off).
There's a UK-government-and-Redwood open-source library of them called ControlArena.

- As written in that library, the four main protocols are fine — no contradictions.
- They're fine because the expensive parts (auditing, budgets, shutdown) are done *after the fact* in
  analysis, not enforced live.
- The moment you enforce those parts live — which any real deployment must — all four break. The common
  hole: every protocol says "audit the suspicious ones" AND "the human audit budget is finite", but none
  says what to do when a must-audit case shows up *after the budget is spent*. At that point the protocol
  has no legal move.
- One protocol (defer-to-resample) contradicts itself even without that, purely as written.

I checked this two completely independent ways that agreed, so it's not a quirk of my method — it's really
in the rules.

## Why it matters to them specifically

AI-safety teams are building "safety cases" — formal arguments that a control protocol keeps a
misaligned AI in check. Every such argument silently assumes the protocol is well-defined (always has a
legal move). Nobody checks that assumption. My tool checks exactly that assumption, and shows it fails on
the field's own reference protocols the moment they're enforced for real.

## The honest limitation (say this yourself — it's a strength, not a weakness)

This is a gap in the *specification*, not a proven exploit. A real deployment probably patches it in code
without writing it down. And the public protocols are either too simple to have interesting conflicts, or
they fix the gap silently. The one thing I can't do from outside is run this on a *real* internal control
stack — the kind with many rules layered together, where a genuine unintended gap would live. That's the
reason to talk to a team that has one.

## How to explain it in one minute (out loud)

"Control rules for AI agents can contradict each other in specific situations, and there's no check for that
before deployment — you find out when the agent gets stuck. I took my thesis engine, which checks whether a
set of rules is jointly satisfiable and suggests the minimal fix, and pointed it at the standard published
control protocols. On their own they're fine, but that's only because the auditing and budget parts are
computed after the fact. Enforce them live, the way a real deployment has to, and all four break the same
way: they say audit the suspicious cases and the audit budget is finite, but never say what to do when a
must-audit case arrives after the budget runs out — so the protocol has no legal move. I verified it two
independent ways. The catch is it's a specification gap on public toy protocols; the value is running it on
a real control stack, which is why I'm reaching out."

## If asked a harder question

- "Isn't this just model checking?" — No. Model checking asks if a given system violates a property.
  This asks whether a valid controller *exists at all* against an adversarial environment. Different
  question; it catches deadlocks that attack-based evaluation structurally can't see.
- "Couldn't a coder just add an else-branch?" — Yes, and they probably do — which is the point: the
  behaviour in that state is then unspecified and left to whoever wrote the code, unaudited, in exactly
  the place a safety case needs it pinned down.
- "How is your thesis engine different from existing repair?" — It finds the fix by walking one failing
  path and interpolating, instead of computing the whole failure set, so it scales where the older
  interpolation method times out. Honestly, I haven't benchmarked it against the newer learning-based
  repair methods — that's an open comparison.

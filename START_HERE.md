# START HERE

Everything we built this week, packaged. You've only ever seen it through the chat; this is the map.

## Read in this order

1. **EXPLAINER.md** — plain English, no maths. What the whole thing is and how to say it out loud.
   Read this first and everything else makes sense.
2. **SAFETYCASE.md** — the main result: control-protocol totality, the finding on ControlArena. One page.
3. **OUTREACH_DRAFT.md** — the message to send to the Control team / Redwood. Not sent yet.
4. **RESULTS.md** — the 23-policy-set corpus results (the broader "does it work" evidence).
5. Supporting, only if you want detail:
   - **CONTROLARENA.md** — the check on AISI's own micro-protocols (clean bill).
   - **EXTERNAL.md** — the test on other people's material (where extraction, not checking, is the weak link).
   - **CLAUDECODE.md** + **HOOK_TEST.md** — the Claude Code permission-system inconsistencies and the live test.
   - **README.md** — how to run the tool.

## What it is, in one line

A tool that checks whether a set of AI-agent control rules can ever contradict each other, shows a worked
example when they do, and proposes the fix — built on my MSc thesis engine.

## The status right now

DONE:
- The tool works, runs from a clean clone, verified.
- Thesis engine revived, three bugs fixed, one benchmark ~1000x faster than the thesis reported.
- The main finding (SAFETYCASE.md), cross-validated two independent ways.
- The outreach message drafted.

NOT DONE — and all three are yours, they need you not me:
1. **Push the repo to GitHub.** It's a "publish", so I won't do it for you. Make an empty repo called
   policy-checker on github.com, then in a terminal:
       cd ~/Documents/policy-checker
       git remote add origin git@github.com:<your-username>/policy-checker.git
       git push -u origin main
   (if `git branch` says "master" not "main", push master instead)
2. **Rotate the Gemini API key** — I pasted it into the chat earlier so it's in the transcript. In Google AI
   Studio, regenerate the key, and put the new one in ~/.config/policy-checker/env
3. **Send the message** (OUTREACH_DRAFT.md) — once the repo's up, drop the link in and send to one person.

## The honest summary

It's a real, working piece of technical work with your name on it — the first thing that answers "what have
you built" rather than "what are you qualified for". It is NOT a big discovery; the finding is a
specification gap on public protocols, and its real value needs a real control stack you can only get by
talking to a team. The point of sending it is to get that conversation.

## Where the files live

All under ~/Documents/policy-checker on your Mac. The engine and the vendored Spectra tools are in there too
(engine/, vendor/) but you don't need to read those — they're machinery.

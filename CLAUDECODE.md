# Claude Code's permission system, checked against its own documentation — 7 September 2026

**Target.** The permission decision Claude Code makes for a single tool call: permission rules (deny / ask /
allow), PreToolUse hooks (exit-2 block, JSON deny / ask / allow), six permission modes, the Bash sandbox's
auto-allow, protected paths, critical paths, tools that require user interaction, and the EndConversation
exception. Six interacting mechanisms in a widely deployed control layer, documented in prose precise enough to
encode sentence by sentence.

**Method.** `policies_claudecode/cc_permissions_literal.yaml`: 21 rules (47 constraints), 25 environment
variables, each rule quoting the sentence it encodes from *Configure permissions* and *Choose a permission mode*
(fetched 7 Sep 2026). Checked for realisability; each conflict adjudicated against the docs — including the
*Hooks* and *Sandboxing* pages — and a resolution applied; repeat until realisable. 20 iterations
(`tools/cc_iterate_resolutions.py` reproduces them; final spec `cc_permissions_resolved.spectra`).

## Tally

| class | count | meaning |
|---|---|---|
| stated precedence my encoding had omitted | 6 | noise: the docs resolve it, I had not carried the qualifier over |
| stated on a *different* page than the rules it qualifies | 5 | the hooks page settles hook-ask-in-bypass, hook-allow-vs-classifier, hook-allow-in-plan-commands, hook-deny |
| **two passages contradict** | **4** | see below |
| **docs silent** | **3** | see below |
| plus 2 | | conflicts I resolved one way that the hooks page then resolved the other way |

## Findings

### Contradictions between pages

1. **Hook `allow` vs permission rules.** *Hooks*: `"allow"` — "Claude Code allows the tool call to proceed
   without prompting, **bypassing the permission system entirely**." *Configure permissions*: "**Hook decisions
   don't bypass permission rules.** Claude Code evaluates deny and ask rules regardless of what a PreToolUse hook
   returns." Both cannot be true. The encoding followed the permissions page.
2. **Bare `Bash` ask rule under the sandbox.** *Choose a permission mode*: "Tools matched by an explicit ask
   rule" are never auto-approved "in any mode". *Sandboxing* / *Configure permissions*: "A bare `Bash` ask rule
   ... is skipped for commands that run sandboxed." Reconcilable only if "explicit" means content-scoped, which
   neither page says.
3. **Plan mode edits vs protected-path writes.** *Plan mode*: "edits stay blocked until you approve the plan."
   *Protected paths* table, row `plan`: "routed to the classifier when auto mode is available during planning,
   and prompted when it isn't." A write to `.claude/settings.json` in plan mode is both blocked and prompted.
4. **Sandbox auto-allow vs the auto-mode classifier.** *Sandboxing*: "Auto-allow mode works independently of
   your permission mode setting, with one exception: plan mode ... sandboxed Bash commands run automatically."
   *Auto mode* decision order: "Everything else goes to the classifier." Whether a sandboxed command in auto
   mode is classifier-reviewed is stated both ways.

### Silences — combinations no page decides

5. **Hook `allow` on a tool that requires user interaction** — TESTED, see HOOK_TEST.md: the ask-rule proxy shows the implementation does NOT let a hook allow bypass the gate; documentation bug, not a bypass.

   Original reading kept below for the record:

    (`AskUserQuestion`, MCP `requiresUserInteraction`,
   connector tools an org set to `ask`). These "prompt you directly even when an allow *rule* matches" and are
   listed under "actions no mode auto-approves"; hooks are not mentioned. Under finding 1's hooks-page reading, a
   hook `allow` skips the consent step; under the permissions-page reading it does not. This is the one with a
   security consequence: an org-required approval on a connector tool is either enforceable against hooks or it
   isn't.
6. **Hook `allow` on a protected-path write.** Critical-path removals say explicitly that no hook `allow`
   approves them; protected paths say "never auto-approved" and "route to the classifier even when an allow rule
   matches", and do not mention hooks.
7. **Hook `allow` / `ask`, or an ask rule, on a file edit in plan mode** without bypass available. Plan mode
   "blocks" edits; whether that block is part of "the permission system" a hook bypasses is not said.

Every one of these is a two-line fix to the docs (or, if the implementation already has an answer, one sentence
stating it). None was visible by reading; each surfaced as a concrete situation the checker constructed —
e.g. "mode = bypassPermissions, hook returned allow, tool is `requiresUserInteraction`: no decision satisfies
every sentence."

## What this is and is not

It is a consistency check of *documentation*, not of the implementation; the code may well resolve all seven
one way or another. It is small in each instance. But it is exactly the shape the checker exists for: many
absolute sentences, written across pages and versions, about a control layer that decides what an agent may do.
Twenty-one rules from the docs of a shipped product produced seven places where two sentences disagree or none
applies, and the counter-trace for each is a test case the maintainers can run.

Encodings, resolutions and the final realisable spec are in `policies_claudecode/` and `tools/`.

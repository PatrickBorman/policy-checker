# Live test of finding 5 — does a PreToolUse hook `allow` bypass an ask rule / consent gate?

Claude Code 2.1.260, on the author's own machine, throwaway `HOME`, no change to real config.
Harness reproduced by `tools/hook_bypass_test.sh` (paths adjusted).

| test | ask rule | hook returns allow | hook fired | command ran |
|---|---|---|---|---|
| C positive control | none | yes | yes | **YES** |
| A | `Bash(touch marker*)` | — | — | no |
| B | `Bash(touch marker*)` | yes | yes | **no** |
| D | bare `Bash` (consent-gate class) | yes | yes | **no** |

C shows the hook's `allow` is honoured when nothing blocks it. B and D show that a matching **ask rule beats a
hook `allow`**: the hook fired and returned allow, and the command was still blocked.

## Result

The implementation resolves the documentation contradiction (finding 1 / finding 5) in the **safe** direction.
*Configure permissions* is correct — "Hook decisions don't bypass permission rules ... a matching ask rule still
prompts even when the hook returned allow" — and the *Hooks* page wording, `allow` "bypassing the permission
system entirely", is imprecise. A PreToolUse hook cannot silently auto-approve an ask-gated tool.

Also confirmed: an **untrusted workspace's project settings are ignored wholesale** (a checked-in `.claude/
settings.json` did not load, hook included, until the workspace was trusted). That trust gate is the real
defence against a repo-shipped auto-allow hook, and it holds.

## Status of the finding

- Finding 5 is a **documentation** inconsistency, not a privilege-escalation bypass. Report to Anthropic as a
  docs fix: state on the Hooks page that `allow` does not override deny/ask rules or the "actions no mode
  auto-approves" list.
- **Not yet tested:** a live MCP tool marked `requiresUserInteraction`, or an org-managed connector set to
  `ask`, as opposed to the ask-rule proxy used here. Same governing list, so almost certainly the same result,
  but unverified.

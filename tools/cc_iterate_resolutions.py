"""Iterate: check the spec, print the core and the losing env situation; apply named resolutions and repeat."""
import sys, json
from pathlib import Path
import os; sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from policy_checker.model import load_yaml, emit_spectra, Constraint
from policy_checker import spectra as S

def run(ps, cons, tag):
    text, lm = emit_spectra(ps, cons)
    p = Path(f'out_cc/{tag}.spectra'); p.parent.mkdir(exist_ok=True); p.write_text(text)
    if S.check_realizable(p, 120):
        print(f"[{tag}] REALISABLE"); return None
    core = sorted({lm.get(i, '?') for i in S.unrealizable_core(p, 120)})
    cs = S.counter_strategy(p, 120)
    path, env_vals, deads = cs.witness()
    env_true = [v for v in ps.env_names if env_vals.get(v)]
    print(f"[{tag}] UNREALISABLE core={core}\n   situation: {', '.join(env_true)}")
    allc = [(c.rule_id, c.kind, c.expr) for c in cons + ps.extra]
    from policy_checker.spectra import explain_dead, CSState
    from itertools import product
    for combo in product([False, True], repeat=len(ps.sys_names)):
        vals = dict(zip(ps.sys_names, combo))
        if sum(combo) > 1: continue
        fake = CSState('_', {**env_vals, **vals}, [])
        why = explain_dead(fake, None, allc, ps.sys_names)
        print(f"   {', '.join(k for k,v in vals.items() if v) or '(nothing)':12s} violates {why}")
    return core

ps = load_yaml('policies_claudecode/cc_permissions_literal.yaml')
cons = ps.manual_constraints()
run(ps, cons, 'tierA')

# ---- Tier B: apply resolutions cumulatively ----
RES = [
 ("R1 DOC-INCONSISTENT: modes page 'explicit ask rule never auto-approved' vs permissions page 'sandboxed Bash runs despite a bare Bash ask rule'. Permissions page distinguishes bare vs scoped; drop A2 (bare) as subsumed by A1 (scoped).",
  lambda cs: [c for c in cs if c.rule_id != 'A2']),
 ("R2 UNRESOLVED: hook 'allow' vs requiresUserInteraction/connector-ask tools. Docs say no allow RULE approves them; silent on hooks. Assume the prompt wins (as stated for critical paths).",
  lambda cs: [Constraint(c.rule_id, c.kind, c.expr.replace("(hook_allow & !deny_rule & !ask_rule & !critical_rm)", "(hook_allow & !deny_rule & !ask_rule & !critical_rm & !mcp_interact)"), c.note) for c in cs]),
 ("R3 DOC-RESOLVED: H3 'ask rule still prompts even when the hook returned allow' vs E1 'an ask rule never prompts for EndConversation'. The exception is stated; add it to H3.",
  lambda cs: [Constraint(c.rule_id, c.kind, c.expr.replace("(hook_allow & ask_rule) -> prompt", "(hook_allow & ask_rule & !end_conv) -> prompt"), c.note) for c in cs]),
 ("R4 UNRESOLVED: a PreToolUse hook that forces a prompt, in bypassPermissions. Bypass 'disables permission prompts'; the list of what still prompts omits hook-forced prompts; dontAsk states its answer, bypass does not. Assume the hook's prompt survives.",
  lambda cs: [Constraint(c.rule_id, c.kind, c.expr.replace("(m_bypass & !ask_rule & !mcp_interact & !critical_rm & !deny_rule & !hook_block & !hook_deny) -> proceed", "(m_bypass & !ask_rule & !mcp_interact & !critical_rm & !deny_rule & !hook_block & !hook_deny & !hook_ask) -> proceed"), c.note) for c in cs]),
 ("R5 DOC-RESOLVED: hook verdicts on EndConversation. Permissions page: 'PreToolUse hooks run ... for every tool except EndConversation'. Add as an environment assumption.",
  lambda cs: cs + [Constraint('X5', 'assumption', 'G (end_conv -> (!hook_block & !hook_deny & !hook_ask & !hook_allow))')]),
 ("R6 DOC-RESOLVED: dontAsk 'auto-denies every tool call that would otherwise prompt you'. Every prompt obligation (hook ask, hook-allow-vs-ask-rule) becomes a denial in dontAsk.",
  lambda cs: sum([[Constraint(c.rule_id, c.kind, "G ((hook_ask & !m_dontask) -> prompt)"), Constraint(c.rule_id, c.kind, "G ((hook_ask & m_dontask) -> block)")] if c.expr == "G (hook_ask -> prompt)" else [Constraint(c.rule_id, c.kind, c.expr.replace("(hook_allow & ask_rule & !end_conv) -> prompt", "(hook_allow & ask_rule & !end_conv & !m_dontask) -> prompt"), c.note)] for c in cs], [])),
 ("R7 UNRESOLVED (same gap as R4): hook-forced prompt vs bypassPermissions 'allowed' outcomes for protected-path writes. Assume the hook's prompt survives.",
  lambda cs: [Constraint(c.rule_id, c.kind, c.expr.replace("(protected_write & m_bypass & !deny_rule & !hook_block & !hook_deny & !ask_rule) -> proceed", "(protected_write & m_bypass & !deny_rule & !hook_block & !hook_deny & !ask_rule & !hook_ask) -> proceed"), c.note) for c in cs]),
 ("R8 DOC-INCONSISTENT: plan mode 'edits stay blocked until you approve the plan' vs protected-paths table 'plan: routed to the classifier when auto is available, prompted when it isn't'. A protected-path write in plan mode is both blocked and prompted/classified. Let the more specific table win.",
  lambda cs: [Constraint(c.rule_id, c.kind, c.expr.replace("(m_plan & is_edit & !bypass_avail) -> block", "(m_plan & is_edit & !bypass_avail & !protected_write) -> block"), c.note) for c in cs]),
 ("R9 UNRESOLVED: hook 'deny' vs a matching ask rule. Docs: ask rules prompt even when the hook returned allow or ask; hook deny not mentioned. Assume deny wins.",
  lambda cs: [Constraint(c.rule_id, c.kind, c.expr.replace("(ask_rule & !end_conv & !m_dontask) -> prompt", "(ask_rule & !end_conv & !m_dontask & !hook_deny & !hook_block) -> prompt"), c.note) for c in cs]),
 ("R10 DOC-RESOLVED: deny rule vs hook 'ask'. 'Claude Code evaluates deny and ask rules regardless of what a PreToolUse hook returns: a matching deny rule blocks the call'. Add deny to the hook-ask exclusions; likewise a matching ask rule (A1) already outranks hook ask.",
  lambda cs: [Constraint(c.rule_id, c.kind, c.expr.replace("G ((hook_ask & !m_dontask) -> prompt)", "G ((hook_ask & !m_dontask & !deny_rule & !hook_block) -> prompt)").replace("G ((ask_rule & !end_conv & m_dontask) -> block)", "G ((ask_rule & !end_conv & m_dontask) -> block)"), c.note) for c in cs]),
 ("R11 DOC-RESOLVED: deny and ask both match. 'Rules are evaluated in order: deny, then ask, then allow. The first match determines the outcome.' Ask obligations exclude a matching deny.",
  lambda cs: [Constraint(c.rule_id, c.kind, c.expr.replace("(ask_rule & !end_conv & !m_dontask & !hook_deny & !hook_block) -> prompt", "(ask_rule & !end_conv & !m_dontask & !hook_deny & !hook_block & !deny_rule) -> prompt").replace("G ((ask_rule & !end_conv & m_dontask) -> block)", "G ((ask_rule & !end_conv & m_dontask) -> block)").replace("(critical_rm & m_auto & ask_rule) -> prompt", "(critical_rm & m_auto & ask_rule & !deny_rule & !hook_block & !hook_deny) -> prompt"), c.note) for c in cs]),
 ("R12 DOC-RESOLVED (same sentence as R11): H3 'ask rule still prompts even when the hook returned allow' presupposes no deny match; deny is evaluated first.",
  lambda cs: [Constraint(c.rule_id, c.kind, c.expr.replace("(hook_allow & ask_rule & !end_conv & !m_dontask) -> prompt", "(hook_allow & ask_rule & !end_conv & !m_dontask & !deny_rule) -> prompt"), c.note) for c in cs]),
 ("R13 UNRESOLVED: hook 'allow' on a protected-path write. Protected paths are 'never auto-approved' and route to the classifier 'even when an allow rule matches'; hooks not mentioned; dontAsk says hook-approved calls run and protected writes are denied. Assume protected wins.",
  lambda cs: [Constraint(c.rule_id, c.kind, c.expr.replace("(hook_allow & !deny_rule & !ask_rule & !critical_rm & !mcp_interact)", "(hook_allow & !deny_rule & !ask_rule & !critical_rm & !mcp_interact & !protected_write)"), c.note) for c in cs]),
 ("R14 UNRESOLVED: sandbox auto-allow (bare Bash ask rule substituted by the sandbox boundary) vs the auto-mode classifier. Sandbox section is written for Manual mode; auto mode's decision order sends 'everything else' to the classifier. Assume the classifier governs in auto.",
  lambda cs: [Constraint(c.rule_id, c.kind, c.expr.replace("(sandboxed & bare_ask & !ask_rule & !deny_rule & !critical_rm & !m_plan & !hook_block & !hook_deny & !hook_ask) -> proceed", "(sandboxed & bare_ask & !ask_rule & !deny_rule & !critical_rm & !m_plan & !m_auto & !m_dontask & !hook_block & !hook_deny & !hook_ask) -> proceed"), c.note) for c in cs]),
 ("R15 UNRESOLVED: hook 'allow' vs the auto-mode classifier. Auto mode's decision order resolves allow/ask/deny RULES in step 1 and sends 'everything else' to the classifier; hooks are not placed in the order. Assume a hook allow resolves like an allow rule.",
  lambda cs: [Constraint(c.rule_id, c.kind, c.expr.replace("(m_auto & is_bash & !critical_rm & !allow_rule & !ask_rule & !deny_rule & !hook_block & !hook_deny & !hook_ask)", "(m_auto & is_bash & !critical_rm & !allow_rule & !ask_rule & !deny_rule & !hook_block & !hook_deny & !hook_ask & !hook_allow)").replace("(m_auto & !classifier_ok & is_bash & !allow_rule & !ask_rule & !deny_rule & !hook_block & !hook_deny & !hook_ask & !critical_rm)", "(m_auto & !classifier_ok & is_bash & !allow_rule & !ask_rule & !deny_rule & !hook_block & !hook_deny & !hook_ask & !hook_allow & !critical_rm)"), c.note) for c in cs]),
 ("R16 UNRESOLVED (same gap as R4/R7): hook-forced prompt vs classifier-routed outcomes (critical-path removals, protected-path writes, plan-mode commands in auto). Assume the hook's prompt survives everywhere.",
  lambda cs: [Constraint(c.rule_id, c.kind, (c.expr.replace("!deny_rule & !hook_block & !hook_deny) -> (proceed <-> classifier_ok)", "!deny_rule & !hook_block & !hook_deny & !hook_ask) -> (proceed <-> classifier_ok)").replace("!deny_rule & !hook_block & !hook_deny & !ask_rule) -> (proceed <-> classifier_ok)", "!deny_rule & !hook_block & !hook_deny & !ask_rule & !hook_ask) -> (proceed <-> classifier_ok)")), c.note) for c in cs]),
 ("R17 UNRESOLVED (hook family): hook 'allow' on a shell command in plan mode. Plan mode says non-read-only commands prompt or go to the classifier; hooks not mentioned. Assume the hook allow lets it run (as in dontAsk, where the docs say hook-approved calls run).",
  lambda cs: [Constraint(c.rule_id, c.kind, c.expr.replace("(m_plan & is_bash & !bypass_avail & auto_avail & !critical_rm & !ask_rule & !deny_rule & !hook_block & !hook_deny & !hook_ask)", "(m_plan & is_bash & !bypass_avail & auto_avail & !critical_rm & !ask_rule & !deny_rule & !hook_block & !hook_deny & !hook_ask & !hook_allow)").replace("(m_plan & is_bash & !bypass_avail & !auto_avail & !critical_rm & !deny_rule & !hook_block & !hook_deny) -> prompt", "(m_plan & is_bash & !bypass_avail & !auto_avail & !critical_rm & !deny_rule & !hook_block & !hook_deny & !hook_allow) -> prompt"), c.note) for c in cs]),
 ("R18 UNRESOLVED (hook family): hook 'allow' or an ask rule on a file edit in plan mode without bypass available. 'Edits stay blocked until you approve the plan' vs hook allow -> proceed / ask rule -> prompt. Assume the mode block wins.",
  lambda cs: [Constraint(c.rule_id, c.kind, c.expr.replace("(hook_allow & !deny_rule & !ask_rule & !critical_rm & !mcp_interact & !protected_write)", "(hook_allow & !deny_rule & !ask_rule & !critical_rm & !mcp_interact & !protected_write & !(m_plan & is_edit & !bypass_avail))").replace("(ask_rule & !end_conv & !m_dontask & !hook_deny & !hook_block & !deny_rule) -> prompt", "(ask_rule & !end_conv & !m_dontask & !hook_deny & !hook_block & !deny_rule & !(m_plan & is_edit & !bypass_avail & !protected_write)) -> prompt"), c.note) for c in cs]),
 ("R19 UNRESOLVED (hook family, same as R18): hook 'ask' on a plan-mode edit. Assume the mode block wins.",
  lambda cs: [Constraint(c.rule_id, c.kind, c.expr.replace("G ((hook_ask & !m_dontask & !deny_rule & !hook_block) -> prompt)", "G ((hook_ask & !m_dontask & !deny_rule & !hook_block & !(m_plan & is_edit & !bypass_avail & !protected_write)) -> prompt)").replace("(hook_allow & ask_rule & !end_conv & !m_dontask & !deny_rule) -> prompt", "(hook_allow & ask_rule & !end_conv & !m_dontask & !deny_rule & !(m_plan & is_edit & !bypass_avail & !protected_write)) -> prompt"), c.note) for c in cs]),
 ("R20 UNRESOLVED (hook family, same as R4): hook-forced prompt vs 'allowed' protected-path write in a plan session with bypass available. Assume the prompt survives.",
  lambda cs: [Constraint(c.rule_id, c.kind, c.expr.replace("(protected_write & m_plan & bypass_avail & !deny_rule & !hook_block & !hook_deny & !ask_rule) -> proceed", "(protected_write & m_plan & bypass_avail & !deny_rule & !hook_block & !hook_deny & !ask_rule & !hook_ask) -> proceed"), c.note) for c in cs]),
]
def apply(cons, upto):
    for desc, f in RES[:upto]:
        cons = f(cons)
    return cons
import sys as _s
upto = int(_s.argv[1]) if len(_s.argv) > 1 else len(RES)
for i in range(1, upto + 1):
    print("\n>>", RES[i-1][0][:110])
    core = run(ps, apply(cons, i), f'tierB{i}')
    if core is None: break

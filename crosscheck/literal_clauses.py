"""Independent cross-check of the safety-case totality finding, WITHOUT Spectra or GR(1).

Each protocol's obligations are written as literal (guard -> required_action) clauses, straight from the source
sentences. We enumerate every boolean environment and, for each, collect the set of actions the clauses REQUIRE
and the set they FORBID. A state is:
  - DEADLOCK  if every available action is forbidden (no legal action exists) -> totality fails
  - CONFLICT  if two clauses require different, mutually exclusive actions in the same state
This is a brute-force semantics, dependent on nothing but Python booleans. If it agrees with the Spectra result,
the finding is a property of the rules, not of the formal encoding.
"""
from itertools import product

def analyse(name, env_vars, actions, clauses, domain=lambda e: True):
    """clauses: list of (id, guard(env)->bool, kind, action) with kind in {'require','forbid'}.
    'require' action a in a state means the chosen action must be a; 'forbid' means it must not be a.
    Exactly-one-action is assumed (a controller picks one action per step)."""
    deadlocks, conflicts = [], []
    for bits in product([False, True], repeat=len(env_vars)):
        e = dict(zip(env_vars, bits))
        if not domain(e):
            continue
        required, forbidden, why = set(), set(), {}
        for cid, guard, kind, act in clauses:
            if guard(e):
                (required if kind == 'require' else forbidden).add(act)
                why.setdefault(act, []).append((cid, kind))
        # a legal action: not forbidden, and if anything is required it must be among the required set
        legal = [a for a in actions if a not in forbidden and (a in required or not required)]
        # if two different actions are required, no single action satisfies both -> conflict
        if len(required) >= 2:
            conflicts.append((e, sorted(required), {a: why[a] for a in required}))
        elif not legal:
            deadlocks.append((e, sorted(forbidden), {a: why.get(a, []) for a in actions}))
    return deadlocks, conflicts


def report(name, env_vars, actions, clauses, domain=lambda e: True):
    d, c = analyse(name, env_vars, actions, clauses, domain)
    print(f"== {name}")
    if not d and not c:
        print("   TOTAL: every environment has a legal action, no contradictions")
    for e, forb, _ in d[:3]:
        on = [k for k, v in e.items() if v]
        print(f"   DEADLOCK at {{{', '.join(on)}}}: every action forbidden ({', '.join(forb)})")
    for e, req, _ in c[:3]:
        on = [k for k, v in e.items() if v]
        print(f"   CONFLICT at {{{', '.join(on)}}}: two actions required at once ({', '.join(req)})")
    return d, c


# ---- sc2 trusted_editing + audit-top-2% + budget ----
E = ['tool_call','above_audit','above_edit','budget_exhausted']
report('sc2_te_audit', E, ['use_untrusted','use_edited','audit','pass_through'], [
    ('L0a', lambda e: not e['tool_call'], 'require', 'pass_through'),
    ('L0b', lambda e: e['tool_call'], 'forbid', 'pass_through'),
    ('G1',  lambda e: e['tool_call'] and e['above_audit'], 'require', 'audit'),
    ('G2',  lambda e: e['tool_call'] and e['above_edit'] and not e['above_audit'], 'require', 'use_edited'),
    ('G3',  lambda e: e['tool_call'] and not e['above_edit'], 'require', 'use_untrusted'),
    ('G4',  lambda e: e['budget_exhausted'], 'forbid', 'audit'),
], domain=lambda e: (not e['above_audit']) or e['above_edit'])

# ---- sc1 defer_to_trusted + audit + shutdown ----
E1 = ['tool_call','above_defer','above_audit','budget_exhausted','excess_suspicion']
report('sc1_dtt_audit_shutdown', E1, ['use_untrusted','use_trusted','audit','shutdown','pass_through'], [
    ('L0a', lambda e: not e['tool_call'], 'require', 'pass_through'),
    ('L0b', lambda e: e['tool_call'], 'forbid', 'pass_through'),
    ('G1',  lambda e: e['excess_suspicion'], 'require', 'shutdown'),
    ('G2',  lambda e: e['tool_call'] and e['above_audit'], 'require', 'audit'),
    ('G3',  lambda e: e['budget_exhausted'], 'forbid', 'audit'),
    ('G4',  lambda e: e['above_defer'], 'forbid', 'use_untrusted'),
], domain=lambda e: ((not e['above_audit']) or e['above_defer']) and ((not e['excess_suspicion']) or e['tool_call']))

# ---- sc3 defer_to_resample + audit-if-min-above ----
E3 = ['tool_call','initial_above_defer','min_resample_above_defer','min_above_audit','budget_exhausted']
report('sc3_dtr_audit', E3, ['use_initial','use_least_sus_resample','use_trusted','audit','pass_through'], [
    ('L0a', lambda e: not e['tool_call'], 'require', 'pass_through'),
    ('L0b', lambda e: e['tool_call'], 'forbid', 'pass_through'),
    ('G1',  lambda e: e['tool_call'] and not e['initial_above_defer'], 'require', 'use_initial'),
    ('G2',  lambda e: e['tool_call'] and e['initial_above_defer'] and e['min_resample_above_defer'], 'require', 'use_trusted'),
    ('G3',  lambda e: e['tool_call'] and e['initial_above_defer'] and not e['min_resample_above_defer'], 'require', 'use_least_sus_resample'),
    ('G4',  lambda e: e['tool_call'] and e['min_above_audit'], 'require', 'audit'),
    ('G5',  lambda e: e['budget_exhausted'], 'forbid', 'audit'),
], domain=lambda e: (not e['min_above_audit']) or (e['initial_above_defer'] and e['min_resample_above_defer']))

# ---- sc4 untrusted_monitoring + honeypot + audit + budget ----
E4 = ['output_ready','honeypot','monitor_flagged','budget_exhausted']
report('sc4_um_honeypot', E4, ['ship','audit','shutdown','none'], [
    ('L0a', lambda e: not e['output_ready'], 'forbid', 'ship'),
    ('L0b', lambda e: not e['output_ready'], 'forbid', 'audit'),
    ('L0c', lambda e: not e['output_ready'], 'forbid', 'shutdown'),
    ('L0d', lambda e: e['output_ready'], 'forbid', 'none'),
    ('G1',  lambda e: e['output_ready'] and e['honeypot'], 'forbid', 'ship'),
    ('G2',  lambda e: e['output_ready'] and e['honeypot'] and not e['monitor_flagged'], 'require', 'shutdown'),
    ('G3',  lambda e: not (e['output_ready'] and e['honeypot'] and not e['monitor_flagged']), 'forbid', 'shutdown'),
    ('G4',  lambda e: e['output_ready'] and e['monitor_flagged'], 'require', 'audit'),
    ('G5',  lambda e: e['budget_exhausted'], 'forbid', 'audit'),
])

"""Natural-language policy rules -> Spectra GR(1) constraints, via Claude with structured output."""
from __future__ import annotations

import json
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from .model import Constraint, PolicySet
from .evaluate import parse, uses_next, temporal_kind

MODEL = "claude-opus-5"

SYSTEM = """You translate natural-language control policies for AI agents into GR(1) specifications in the
Spectra language, so that a solver can check whether the policy set is jointly *realisable*: whether a
controller strategy exists that satisfies every rule no matter what the environment does.

# The two-player setting
- ENVIRONMENT variables (env): what the agent under control proposes and what the world does (user actions,
  monitor verdicts, resource state). The controller cannot choose these. The environment is adversarial.
- SYSTEM variables (sys): the controller's decisions. In each step the environment moves first and the
  controller then chooses its sys values *in the same step*, having seen the current env values.
- A rule that constrains the ENVIRONMENT ("the user only confirms when...", "once the budget is exhausted it
  stays exhausted") is an `assumption`. A rule that constrains the CONTROLLER is a `guarantee`. Almost all
  policy rules are guarantees. If a rule mixes both, split it.

# Spectra subset you may use
- Variables are the declared booleans only. Never invent variables. Use exact names.
- Connectives: `!`, `&`, `|`, `->`, `<->`, parentheses. Constants `true`, `false`.
- Temporal forms, one per constraint:
    * initial constraint: a plain boolean expression (holds in the first step only)
    * safety: `G ( ... )` holds in every step; inside it `next(v)` refers to v in the following step
    * justice (liveness): `GF ( ... )` holds infinitely often
- Assumptions must not contain `next()` of a sys variable. Guarantees may use `next()` of any variable.
- "In the same step" needs no temporal operator: `G (req -> (allow | block))`.
- "Never X after Y" / "not twice in a row": use next(): `G (escalate -> !next(escalate))`.
- "Eventually" / "infinitely often": `GF (...)`. There are no bounded-time operators ("within 3 steps") and no
  new state variables: encode the closest GR(1) meaning and set approximate=true with a note.
- Exclusivity / "exactly one of" must be written out: `G (!(a & b) & !(a & c) & !(b & c))` plus the
  "at least one" disjunction, plus what holds when nothing is requested if the rule says so.

# Output
For every rule, return kind, one or more Spectra expressions (no trailing semicolon), a one-line note on the
reading you chose, and approximate=true if the encoding is weaker or stronger than the sentence.
Be literal. Do not add rules that are not stated. Do not "fix" contradictions between rules - finding
them is the point.

# Example
Variables: env: req_pay (the agent proposes a payment), amount_high (the amount is above the limit),
manager_ok (a manager approved this step). sys: approve, reject.
Rules:
 R1 "Every payment proposal is either approved or rejected in the same step, never both; no decision without a proposal."
   -> guarantee: G (req_pay -> (approve | reject)) ; G (!(approve & reject)) ; G (!req_pay -> (!approve & !reject))
 R2 "High-value payments are never approved without a manager's approval in the same step."
   -> guarantee: G ((req_pay & amount_high & !manager_ok) -> !approve)
 R3 "A manager only approves when there is a proposal."
   -> assumption: G (manager_ok -> req_pay)
 R4 "Do not reject the same customer twice in a row."
   -> guarantee: G (reject -> !next(reject))   note: 'same customer' is not representable; encoded as consecutive steps; approximate=true
"""


class TranslatedRule(BaseModel):
    id: str = Field(description="the rule id exactly as given")
    kind: Literal["assumption", "guarantee"]
    spectra: List[str] = Field(description="one or more Spectra expressions, no trailing semicolon")
    note: str = Field(description="one line: the reading you chose, and anything lost in translation")
    approximate: bool = False


class Translation(BaseModel):
    rules: List[TranslatedRule]


def _prompt(ps: PolicySet) -> str:
    env = "\n".join(f"  - {v.name}: {v.desc}" for v in ps.env)
    sys = "\n".join(f"  - {v.name}: {v.desc}" for v in ps.sys)
    rules = "\n".join(f"  {r.id}" + (f" [{r.kind}]" if r.kind else "") + f': "{r.text}"' for r in ps.rules)
    return (f"Policy set: {ps.name}\n{ps.description}\n\nENVIRONMENT variables (the controller cannot choose these):\n{env}\n\n"
            f"SYSTEM variables (the controller's decisions):\n{sys}\n\nRules to translate (a [kind] in brackets is fixed; otherwise decide):\n{rules}\n\n"
            "Translate every rule.")


def validate(ps: PolicySet, tr: Translation) -> List[str]:
    """Static checks before we hand the spec to Spectra. Returns a list of problems (empty = fine)."""
    problems = []
    declared = set(ps.env_names) | set(ps.sys_names)
    ids = {r.id for r in ps.rules}
    seen = set()
    for t in tr.rules:
        if t.id not in ids:
            problems.append(f"{t.id}: unknown rule id")
            continue
        seen.add(t.id)
        fixed = next(r.kind for r in ps.rules if r.id == t.id)
        if fixed and fixed != t.kind:
            problems.append(f"{t.id}: kind {t.kind} but the policy fixes {fixed}")
        for e in t.spectra:
            try:
                ast = parse(e)
            except ValueError as ex:
                problems.append(f"{t.id}: cannot parse {e!r}: {ex}")
                continue
            for name in _vars(ast):
                if name not in declared:
                    problems.append(f"{t.id}: undeclared variable {name!r} in {e!r}")
            if t.kind == "assumption" and uses_next(ast):
                for name in _next_vars(ast):
                    if name in ps.sys_names:
                        problems.append(f"{t.id}: assumption uses next({name}) of a sys variable")
    for r in ps.rules:
        if r.id not in seen:
            problems.append(f"{r.id}: not translated")
    return problems


def _vars(e):
    if e.kind == "var":
        return [e.args[0]]
    out = []
    for a in e.args:
        if hasattr(a, "kind"):
            out += _vars(a)
    return out


def _next_vars(e, inside=False):
    if e.kind == "var":
        return [e.args[0]] if inside else []
    out = []
    for a in e.args:
        if hasattr(a, "kind"):
            out += _next_vars(a, inside or e.kind == "next")
    return out


def translate(ps: PolicySet, client=None, model: str = MODEL, effort: str = "high", retries: int = 1) -> Translation:
    """Call Claude. On validation problems, feed them back once and retry."""
    import anthropic
    client = client or anthropic.Anthropic()
    messages = [{"role": "user", "content": _prompt(ps)}]
    last = None
    for attempt in range(retries + 1):
        resp = client.messages.parse(
            model=model,
            max_tokens=16000,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
            output_format=Translation,
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"model refused: {getattr(resp, 'stop_details', None)}")
        tr: Translation = resp.parsed_output
        last = tr
        problems = validate(ps, tr)
        if not problems:
            return tr
        messages += [
            {"role": "assistant", "content": json.dumps(tr.model_dump())},
            {"role": "user", "content": "Problems with that translation:\n- " + "\n- ".join(problems) + "\nReturn the full corrected translation."},
        ]
    raise ValueError("translation still invalid after retry:\n- " + "\n- ".join(validate(ps, last)))


def to_constraints(tr: Translation) -> List[Constraint]:
    out = []
    for t in tr.rules:
        for e in t.spectra:
            out.append(Constraint(t.id, t.kind, e.strip().rstrip(";"), t.note, t.approximate))
    return out

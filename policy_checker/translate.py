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
- A rule about how a request is handled ("when the kill switch is on, every call is denied", "flagged outputs
  are audited") applies only in steps where there IS a request/output. Put the request variable in the
  antecedent: `G ((req & kill_switch) -> deny)`, not `G (kill_switch -> deny)` - the latter forces a decision
  in steps with nothing to decide and manufactures a conflict with the "nothing without a request" rule.
  Prohibitions ("never allow X") are fine without it: `G (kill_switch -> !allow)`.
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
(In this example note R2 is a prohibition, so no `req_pay` is needed in its antecedent; a positive obligation
like "high-value payments are rejected" would be `G ((req_pay & amount_high & !manager_ok) -> reject)`.)
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


def make_client():
    """Anthropic API if ANTHROPIC_API_KEY is set; otherwise Claude on Vertex AI (Google Cloud credits).

    Vertex needs: `gcloud auth application-default login`, GOOGLE_CLOUD_PROJECT (or POLICY_CHECKER_GCP_PROJECT),
    and the Claude models enabled in Vertex Model Garden. Region defaults to "global".
    """
    import os
    import anthropic
    provider = os.environ.get("POLICY_CHECKER_PROVIDER")
    if provider == "anthropic" or (provider is None and os.environ.get("ANTHROPIC_API_KEY")):
        return anthropic.Anthropic()
    if provider == "gemini" or (provider is None and (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))):
        return GeminiClient()
    project = os.environ.get("POLICY_CHECKER_GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID")
    if not project:
        raise RuntimeError("no credentials: set ANTHROPIC_API_KEY, or for Vertex set GOOGLE_CLOUD_PROJECT and run "
                           "`gcloud auth application-default login`")
    region = os.environ.get("CLOUD_ML_REGION", "global")
    from anthropic import AnthropicVertex
    return AnthropicVertex(project_id=project, region=region)


GEMINI_MODEL = "gemini-3.5-flash"   # free tier; 2.5-pro has a free-tier limit of 0
GEMINI_FALLBACKS = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash-lite"]


class GeminiClient:
    """Same job as the Claude call, on the Gemini API (free tier is enough for this). Structured JSON output."""

    def __init__(self, model: str = None):
        import os
        from google import genai
        self.model = model or os.environ.get("POLICY_CHECKER_GEMINI_MODEL", GEMINI_MODEL)
        self.client = genai.Client()   # reads GEMINI_API_KEY / GOOGLE_API_KEY

    def complete(self, messages) -> Translation:
        """Free-tier daily quotas are small (20/day on 3.5-flash); on a per-day 429 move to the next model."""
        from google.genai import errors
        while True:
            try:
                return self._complete(messages)
            except errors.ClientError as e:
                msg = str(e)
                if "429" in msg and "PerDay" in msg:
                    nxt = [m for m in GEMINI_FALLBACKS if m != self.model and GEMINI_FALLBACKS.index(m) > GEMINI_FALLBACKS.index(self.model)] if self.model in GEMINI_FALLBACKS else []
                    if not nxt:
                        raise
                    self.model = nxt[0]
                    continue
                if "429" in msg:
                    import re, time
                    m = re.search(r"retry in ([\d.]+)s", msg)
                    time.sleep(min(float(m.group(1)) if m else 20, 65) + 1)
                    continue
                raise

    def _complete(self, messages) -> Translation:
        from google.genai import types
        contents = [types.Content(role=("user" if m["role"] == "user" else "model"),
                                  parts=[types.Part.from_text(text=m["content"])]) for m in messages]
        resp = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM,
                response_mime_type="application/json",
                response_schema=Translation,
                temperature=0,
            ),
        )
        return Translation.model_validate_json(resp.text)


def _complete_claude(client, messages, model, effort) -> Translation:
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
    return resp.parsed_output


def translate(ps: PolicySet, client=None, model: str = MODEL, effort: str = "high", retries: int = 1) -> Translation:
    """Translate with whichever LLM is configured. On validation problems, feed them back once and retry."""
    client = client or make_client()
    messages = [{"role": "user", "content": _prompt(ps)}]
    last = None
    for attempt in range(retries + 1):
        if isinstance(client, GeminiClient):
            tr = client.complete(messages)
        else:
            tr = _complete_claude(client, messages, model, effort)
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

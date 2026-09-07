"""Raw policy prose -> a PolicySet (variables + rules), by LLM. The external-source test: nothing hand-written."""
from __future__ import annotations

from typing import List

import yaml
from pydantic import BaseModel, Field

from .translate import make_client, GeminiClient

EXTRACT_SYSTEM = """You read a description of a control protocol or permission policy for an AI system and extract it as a
finite-state rule set for a realisability check. Be faithful to the text: extract the rules it states, not the rules
you think it should have. Do not add rules. Do not resolve ambiguities silently - keep the rule as written and note
the ambiguity.

Modelling conventions:
- ENVIRONMENT variables (boolean): things the controller observes but does not choose - the untrusted model's
  outputs, monitor verdicts (e.g. "score above the deferral threshold"), resource state (budget exhausted), user
  actions, which rule patterns a request matches. Thresholds become booleans ("above_audit_threshold").
- SYSTEM variables (boolean): the controller's decisions in a step - submit/ship, defer, audit, resample,
  shut down, allow, deny, ask, block.
- Counts and budgets become booleans for their exhausted/limit state ("budget_exhausted", "resamples_exhausted").
- Every extracted rule is one sentence in plain English about these variables, close to the source wording.
  Include the implicit rule "the controller does exactly one of its actions per step" only if the text implies
  decisions are mutually exclusive.
- Variable names: lowercase identifiers, letters/digits/underscore only, no spaces.
"""


class VarSpec(BaseModel):
    name: str
    desc: str


class RuleSpec(BaseModel):
    id: str
    text: str
    source_quote: str = Field(description="the fragment of the source this rule comes from")
    ambiguity: str = Field(default="", description="what the source leaves unspecified, if anything")


class Extraction(BaseModel):
    name: str = Field(description="identifier for this policy set, e.g. trusted_monitoring_greenblatt")
    description: str
    env: List[VarSpec]
    sys: List[VarSpec]
    rules: List[RuleSpec]


def extract(text: str, focus: str, client=None) -> Extraction:
    client = client or make_client()
    prompt = (f"Extract the rule set for: {focus}\n\nSOURCE TEXT:\n{text}\n\nReturn the variables and rules.")
    if isinstance(client, GeminiClient):
        from google.genai import types
        return client.structured(EXTRACT_SYSTEM, [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])], Extraction)
    resp = client.messages.parse(model="claude-opus-5", max_tokens=16000, system=EXTRACT_SYSTEM,
                                 messages=[{"role": "user", "content": prompt}], thinking={"type": "adaptive"},
                                 output_format=Extraction)
    return resp.parsed_output


def to_yaml(e: Extraction, provenance: str) -> str:
    import re
    name = re.sub(r"[^A-Za-z0-9_]", "_", e.name)
    d = {"name": name, "description": e.description, "provenance": provenance,
         "env": [{"name": v.name, "desc": v.desc} for v in e.env],
         "sys": [{"name": v.name, "desc": v.desc} for v in e.sys],
         "rules": [{"id": r.id, "text": r.text, "source": r.source_quote, **({"ambiguity": r.ambiguity} if r.ambiguity else {})} for r in e.rules]}
    return yaml.safe_dump(d, sort_keys=False, allow_unicode=True, width=110)

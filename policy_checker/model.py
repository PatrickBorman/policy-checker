"""Data model for a policy set and its Spectra encoding."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass
class Var:
    name: str
    desc: str = ""


@dataclass
class Rule:
    id: str
    text: str
    kind: Optional[str] = None            # "assumption" | "guarantee" | None (let the translator decide)
    spectra: Optional[List[str]] = None   # hand-written encoding, used with --no-llm and as a reference


@dataclass
class Constraint:
    """One Spectra constraint attributed to a rule."""
    rule_id: str
    kind: str          # assumption | guarantee
    expr: str          # Spectra expression, no trailing ';'
    note: str = ""
    approximate: bool = False


@dataclass
class PolicySet:
    name: str
    description: str
    env: List[Var]
    sys: List[Var]
    rules: List[Rule]
    extra: List[Constraint] = field(default_factory=list)   # structural constraints written directly in Spectra
    source: Optional[Path] = None

    @property
    def env_names(self):
        return [v.name for v in self.env]

    @property
    def sys_names(self):
        return [v.name for v in self.sys]

    def manual_constraints(self) -> List[Constraint]:
        """Constraints from the hand-written `spectra:` fields (the --no-llm path)."""
        out: List[Constraint] = []
        for r in self.rules:
            if not r.spectra:
                raise ValueError(f"rule {r.id} has no hand-written spectra encoding; run with the translator")
            if r.kind not in ("assumption", "guarantee"):
                raise ValueError(f"rule {r.id} needs kind: assumption|guarantee for the manual path")
            for e in r.spectra:
                out.append(Constraint(r.id, r.kind, e.strip().rstrip(";")))
        return out


def _vars(items) -> List[Var]:
    out = []
    for it in items or []:
        if isinstance(it, str):
            name, desc = it, ""
        else:
            name, desc = it["name"], it.get("desc", "")
        if not IDENT.match(name):
            raise ValueError(f"bad variable name {name!r}")
        out.append(Var(name, desc))
    return out


def load_yaml(path) -> PolicySet:
    path = Path(path)
    d = yaml.safe_load(path.read_text())
    rules = []
    for i, r in enumerate(d.get("rules", [])):
        rid = str(r.get("id", f"R{i+1}"))
        sp = r.get("spectra")
        if isinstance(sp, str):
            sp = [sp]
        rules.append(Rule(rid, r["text"].strip(), r.get("kind"), sp))
    extra = []
    for i, e in enumerate(d.get("extra", [])):
        extra.append(Constraint(f"X{i+1}", e["kind"], e["spectra"].strip().rstrip(";"), e.get("note", "")))
    name = d.get("name") or path.stem
    if not IDENT.match(name):
        raise ValueError(f"policy set name must be an identifier, got {name!r}")
    return PolicySet(name, d.get("description", "").strip(), _vars(d.get("env")), _vars(d.get("sys")), rules, extra, path)


def emit_spectra(ps: PolicySet, constraints: List[Constraint]) -> Tuple[str, Dict[int, str]]:
    """Render a .spectra file. Returns (text, {0-based line index of each constraint expression: rule_id}).

    The line map is what Spectra's unrealizable-core output refers to.
    """
    lines: List[str] = [f"module {ps.name}", ""]
    for v in ps.env:
        lines.append(f"env boolean {v.name};")
    for v in ps.sys:
        lines.append(f"sys boolean {v.name};")
    lines.append("")
    line_map: Dict[int, str] = {}
    for c in list(constraints) + list(ps.extra):
        lines.append(f"// {c.rule_id}" + (f" (approximate)" if c.approximate else ""))
        lines.append(c.kind)
        line_map[len(lines)] = c.rule_id
        lines.append(f"\t{c.expr};")
    lines.append("")
    return "\n".join(lines), line_map

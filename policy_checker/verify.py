"""Independent checks on the checker's own claims.

For every unrealisable set (hand-written encodings):
  1. core minimality by deletion: dropping any single core rule makes the set realisable, and dropping a
     non-core rule does not (so the core is exactly the conflict);
  2. repair validity: the engine's proposed assumption, appended to the ORIGINAL spec, makes it realisable
     according to a fresh Spectra check (not the engine's own bookkeeping);
  3. repair non-vacuity: the repaired spec is satisfiable, i.e. the assumption does not just forbid the
     environment from ever acting.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List

from .model import Constraint, PolicySet, emit_spectra, load_yaml
from . import spectra as S
from . import repair as R


def _check(ps: PolicySet, cons: List[Constraint], out: Path, tag: str, timeout: int) -> bool:
    text, _ = emit_spectra(ps, cons)
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"{ps.name}.{tag}.spectra"
    p.write_text(text)
    return S.check_realizable(p, timeout)


def verify_one(path: Path, out: Path, timeout: int = 120) -> Dict:
    ps = load_yaml(path)
    cons = ps.manual_constraints()
    out.mkdir(parents=True, exist_ok=True)
    text, line_map = emit_spectra(ps, cons)
    spec = out / f"{ps.name}.manual.spectra"
    spec.write_text(text)
    res = {"policy_set": ps.name, "realizable": S.check_realizable(spec, timeout)}
    if res["realizable"]:
        return res
    core = sorted({line_map.get(i, "?") for i in S.unrealizable_core(spec, timeout)})
    res["core"] = core
    rule_ids = [r.id for r in ps.rules]

    # 1. deletion test
    deletion = {}
    for rid in rule_ids:
        rest = [c for c in cons if c.rule_id != rid]
        deletion[rid] = _check(ps, rest, out / "verify", f"minus_{rid}", timeout)
    res["realizable_without"] = deletion
    res["core_minimal"] = all(deletion[r] for r in core if r in deletion)
    res["core_complete"] = all(not deletion[r] for r in rule_ids if r not in core and deletion.get(r) is not None
                               and next(c.kind for c in cons if c.rule_id == r) == "guarantee")

    # 2 + 3. repair validity
    t0 = time.time()
    rep = R.run(spec, out / "repair", timeout_min=2.0)
    res["repair_seconds"] = round(time.time() - t0, 2)
    res["repairs"] = rep["repairs"]
    if rep["repairs"]:
        added = [Constraint(f"REPAIR{i+1}", "assumption", r) for i, r in enumerate(rep["repairs"])]
        repaired_real = _check(ps, cons + added, out / "verify", "repaired", timeout)
        res["repair_valid"] = repaired_real
        rp = out / "verify" / f"{ps.name}.repaired.spectra"
        res["repair_satisfiable"] = S._result(S._run("sat", rp, timeout)) == "true"
    return res


def verify_all(policy_dir: Path, out: Path, timeout: int = 120) -> List[Dict]:
    results = []
    for p in sorted(policy_dir.glob("*.yaml")):
        r = verify_one(p, out, timeout)
        results.append(r)
        if r["realizable"]:
            print(f"{r['policy_set']:32s} realisable")
        else:
            flags = []
            flags.append("core minimal" if r["core_minimal"] else "CORE NOT MINIMAL")
            flags.append("core complete" if r["core_complete"] else "CORE NOT COMPLETE")
            if r["repairs"]:
                flags.append("repair valid" if r["repair_valid"] else "REPAIR INVALID")
                flags.append("non-vacuous" if r["repair_satisfiable"] else "REPAIR VACUOUS")
            else:
                flags.append("NO REPAIR FOUND")
            print(f"{r['policy_set']:32s} core={','.join(r['core'])}  {' | '.join(flags)}  ({r['repair_seconds']}s)")
            for rep in r["repairs"]:
                print(f"{'':32s}   assumption {rep};")
    (out / "verify.json").write_text(json.dumps(results, indent=2))
    return results

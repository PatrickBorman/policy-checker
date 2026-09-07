"""policy-check: NL control policies -> GR(1) -> realisability, counter-trace, core, (repair).

  python -m policy_checker check policies/email_agent.yaml            # translate with Claude, then check
  python -m policy_checker check policies/email_agent.yaml --no-llm   # use the hand-written spectra: fields
  python -m policy_checker batch policies/ [--no-llm]                  # all sets, summary table
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .model import PolicySet, emit_spectra, load_yaml
from . import spectra as S
from . import repair as R


def check_one(path: Path, out_dir: Path, use_llm: bool, model: str, timeout: int, do_repair: bool) -> dict:
    ps = load_yaml(path)
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = "llm" if use_llm else "manual"
    res = {"policy_set": ps.name, "source": str(path), "mode": tag, "rules": len(ps.rules)}

    t0 = time.time()
    if use_llm:
        from .translate import translate, to_constraints
        tr = translate(ps, model=model)
        (out_dir / f"{ps.name}.translation.json").write_text(json.dumps(tr.model_dump(), indent=2))
        constraints = to_constraints(tr)
        res["approximate_rules"] = [t.id for t in tr.rules if t.approximate]
    else:
        constraints = ps.manual_constraints()
    res["t_translate_s"] = round(time.time() - t0, 2)

    text, line_map = emit_spectra(ps, constraints)
    spec = out_dir / f"{ps.name}.{tag}.spectra"
    spec.write_text(text)
    res["spectra"] = str(spec)

    t1 = time.time()
    try:
        realizable = S.check_realizable(spec, timeout)
    except S.SpectraError as e:
        res["error"] = str(e)
        return res
    res["realizable"] = realizable
    res["t_check_s"] = round(time.time() - t1, 2)
    if realizable:
        if use_llm and all(r.spectra for r in ps.rules):
            mtext, _ = emit_spectra(ps, ps.manual_constraints())
            mspec = out_dir / f"{ps.name}.manual.spectra"; mspec.write_text(mtext)
            res["manual_realizable"] = S.check_realizable(mspec, timeout)
            res["agrees_with_manual"] = res["manual_realizable"] is True
        return res

    res["y_sat"] = S.check_y_sat(spec, timeout)
    core_lines = S.unrealizable_core(spec, timeout)
    res["core_rules"] = sorted({line_map.get(i, f"line{i}") for i in core_lines})
    cs = S.counter_strategy(spec, timeout)
    trace = S.render_trace(cs, ps.env_names, ps.sys_names, [(c.rule_id, c.kind, c.expr) for c in list(constraints) + ps.extra])
    res["counter_trace"] = trace
    (out_dir / f"{ps.name}.{tag}.counterstrategy.txt").write_text(cs.raw)

    if use_llm and all(r.spectra for r in ps.rules):
        # translation fidelity: does the LLM encoding reach the same verdict and core as the hand-written one?
        mtext, mmap = emit_spectra(ps, ps.manual_constraints())
        mspec = out_dir / f"{ps.name}.manual.spectra"
        mspec.write_text(mtext)
        mreal = S.check_realizable(mspec, timeout)
        res["manual_realizable"] = mreal
        if not mreal:
            res["manual_core_rules"] = sorted({mmap.get(i, f"line{i}") for i in S.unrealizable_core(mspec, timeout)})
        res["agrees_with_manual"] = (mreal == realizable) and (mreal or res.get("core_rules") == res.get("manual_core_rules"))

    if do_repair:
        try:
            rep = R.run(spec, out_dir / "repair")
            res["repairs"] = rep["repairs"]
            res["t_repair_s"] = rep["seconds"]
            res["repair_nodes"] = rep["nodes"]
            (out_dir / f"{ps.name}.{tag}.repair.log").write_text(rep["log"])
        except Exception as e:
            res["repair_error"] = str(e)
    return res


def render(res: dict, ps_desc: str = "") -> str:
    L = [f"# {res['policy_set']}  ({res['mode']}, {res['rules']} rules)"]
    if "error" in res:
        return "\n".join(L + [f"ERROR: {res['error']}"])
    if res.get("approximate_rules"):
        L.append(f"approximate encodings: {', '.join(res['approximate_rules'])}")
    if "agrees_with_manual" in res:
        L.append("translation vs hand-written encoding: " + ("same verdict and core" if res["agrees_with_manual"] else
                 f"DISAGREES (manual: {'realisable' if res['manual_realizable'] else 'unrealisable core=' + ','.join(res.get('manual_core_rules', []))})"))
    if res["realizable"]:
        L.append(f"REALISABLE - a controller exists that satisfies every rule against any environment.  ({res['t_check_s']}s)")
        return "\n".join(L)
    L.append(f"UNREALISABLE  ({res['t_check_s']}s)")
    if not res.get("y_sat", True):
        L.append("The guarantees contradict each other outright - no assumption about the environment can fix this.")
    L.append(f"conflicting rules (minimal core): {', '.join(res['core_rules'])}")
    L.append("counter-trace - a run the environment can force:")
    L.append(res["counter_trace"])
    if "repairs" in res:
        if res["repairs"]:
            L.append(f"minimal repair - add this assumption about the environment and every rule becomes enforceable  ({res['t_repair_s']}s, {res['repair_nodes']} candidates):")
            for r in res["repairs"]:
                L.append(f"    assumption {r};")
        else:
            L.append(f"repair: none found within the budget ({res['t_repair_s']}s, {res['repair_nodes']} candidates)")
    if "repair_error" in res:
        L.append(f"repair: not run - {res['repair_error']}")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="policy-check", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "batch"):
        p = sub.add_parser(name)
        p.add_argument("path")
        p.add_argument("--no-llm", action="store_true", help="use the hand-written spectra: fields instead of Claude")
        p.add_argument("--model", default="claude-opus-5")
        p.add_argument("--out", default="out")
        p.add_argument("--timeout", type=int, default=120, help="seconds per Spectra call")
        p.add_argument("--repair", action="store_true", help="run the interpolation repair engine on unrealisable sets")
        p.add_argument("--json", action="store_true", help="print JSON instead of text")
    a = ap.parse_args(argv)
    out = Path(a.out)
    paths = [Path(a.path)] if a.cmd == "check" else sorted(Path(a.path).glob("*.yaml"))
    results = []
    for p in paths:
        r = check_one(p, out, not a.no_llm, a.model, a.timeout, a.repair)
        results.append(r)
        if not a.json:
            print(render(r)); print()
    if a.json:
        print(json.dumps(results, indent=2))
    elif a.cmd == "batch":
        n = len(results); unreal = [r for r in results if r.get("realizable") is False]
        print(f"== {n} policy sets, {len(unreal)} unrealisable ({100*len(unreal)/n:.0f}%)")
        for r in results:
            status = "ERROR" if "error" in r else ("REALISABLE" if r["realizable"] else f"UNREALISABLE core={','.join(r['core_rules'])}")
            if r.get("repairs"):
                status += f"  repaired by: {r['repairs'][0]}"
            if "agrees_with_manual" in r:
                status += "  [translation " + ("agrees" if r["agrees_with_manual"] else "DISAGREES") + " with manual]"
            print(f"   {r['policy_set']:32s} {status}")
    (out / "results.json").write_text(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

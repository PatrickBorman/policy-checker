"""Hook into the interpolation-based assumption-refinement engine (the MSc thesis code).

The engine lives in ~/Documents/interpolation-repair/interpolation-repair and needs:
  - the py38 conda env (jpype, spot, pyparsing)
  - MathSAT 4 for interpolants. The bundled binary is Linux x86-64; on macOS this step is unavailable.
On macOS the engine's hardcoded MathSAT path holds a Python stand-in (BDD-based Craig interpolant) instead.
"""
from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import Optional

ENGINE_DIR = Path(os.environ.get("POLICY_CHECKER_ENGINE_DIR",
                                 Path.home() / "Documents/interpolation-repair/interpolation-repair"))
PY38 = Path(os.environ.get("POLICY_CHECKER_PY38", "/opt/anaconda3/envs/py38/bin/python"))
MATHSAT = ENGINE_DIR / "MathSAT4/mathsat-4.2.17-linux-x86_64/bin/mathsat"


def available() -> Optional[str]:
    """None if the repair engine can run here, else the reason it cannot."""
    if not ENGINE_DIR.exists():
        return f"engine not found at {ENGINE_DIR}"
    if not PY38.exists():
        return f"py38 interpreter not found at {PY38}"
    if not MATHSAT.exists():
        return f"MathSAT (or the BDD stand-in) not found at {MATHSAT}"
    return None


def run(spec: Path, out_dir: Path, timeout_min: float = 2.0, repair_limit: int = 1) -> dict:
    """Run interpolation_repair.py on an unrealisable spec.

    Returns {"repairs": [list of Spectra assumption strings], "nodes": n, "seconds": t, "log": stdout}.
    """
    why = available()
    if why:
        raise RuntimeError(why)
    cmd = [str(PY38), "interpolation_repair.py", "-i", str(spec.resolve()), "-o", str(out_dir.resolve()),
           "-t", str(timeout_min), "-rl", str(repair_limit), "-min", "-inf"]
    env = dict(os.environ)
    cudd = os.environ.get("POLICY_CHECKER_CUDD_DIR", str(Path.home() / "amba-fix"))
    env["JAVA_TOOL_OPTIONS"] = (env.get("JAVA_TOOL_OPTIONS", "") + f" -Djava.library.path={cudd}").strip()
    import csv, io, time
    out_dir.mkdir(parents=True, exist_ok=True)   # the engine hangs if the output folder is missing
    t0 = time.time()
    p = subprocess.run(cmd, cwd=ENGINE_DIR, capture_output=True, text=True, timeout=timeout_min * 60 + 120, env=env)
    log = p.stdout + ("\n[stderr]\n" + p.stderr if p.returncode else "")
    repairs, nodes = [], 0
    nodes_csv = out_dir / f"{spec.stem}_interpolation_nodes.csv"
    if nodes_csv.exists():
        for row in csv.DictReader(io.StringIO(nodes_csv.read_text())):
            nodes += 1
            if row.get("IsSolution") == "True":
                # Refinement is a Python-list repr of Spectra-ish strings using X() for next()
                import ast
                for r in ast.literal_eval(row["Refinement"]):
                    repairs.append(r.replace("X(", "next("))
    return {"repairs": repairs, "nodes": nodes, "seconds": round(time.time() - t0, 2), "log": log}

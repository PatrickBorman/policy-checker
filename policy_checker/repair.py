"""Hook into the interpolation-based assumption-refinement engine (the MSc thesis code).

The engine lives in ~/Documents/interpolation-repair/interpolation-repair and needs:
  - the py38 conda env (jpype, spot, pyparsing)
  - MathSAT 4 for interpolants. The bundled binary is Linux x86-64; on macOS this step is unavailable.
We detect that and report rather than pretend.
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
    if platform.system() != "Linux":
        return "MathSAT 4 interpolation binary is Linux-only; run the repair step on Linux (or port to pysmt+MathSAT5)"
    if not MATHSAT.exists():
        return f"MathSAT not found at {MATHSAT}"
    return None


def run(spec: Path, out_dir: Path, timeout_min: float = 2.0, repair_limit: int = 1) -> str:
    """Run interpolation_repair.py on an unrealisable spec. Returns its stdout."""
    why = available()
    if why:
        raise RuntimeError(why)
    cmd = [str(PY38), "interpolation_repair.py", "-i", str(spec.resolve()), "-o", str(out_dir.resolve()),
           "-t", str(timeout_min), "-rl", str(repair_limit), "-min", "-inf"]
    p = subprocess.run(cmd, cwd=ENGINE_DIR, capture_output=True, text=True, timeout=timeout_min * 60 + 120)
    return p.stdout + ("\n[stderr]\n" + p.stderr if p.returncode else "")

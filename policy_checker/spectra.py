"""Drive Spectra (via java/SpecCheck) as a subprocess: realisability, Y-sat, unrealizable core, counter-strategy."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

HERE = Path(__file__).resolve().parent.parent

# Locations. Everything needed is vendored under the repo; override with env vars if the layout differs.
import shutil


def _find_java() -> str:
    if os.environ.get("POLICY_CHECKER_JAVA"):
        return os.environ["POLICY_CHECKER_JAVA"]
    if os.environ.get("JAVA_HOME"):
        return str(Path(os.environ["JAVA_HOME"]) / "bin/java")
    import subprocess as sp
    conda = os.environ.get("CONDA_PREFIX") or str(Path(sys.executable).parent.parent)
    for cand in (str(Path(conda) / "lib/jvm/bin/java"), shutil.which("java"),
                 "/opt/homebrew/opt/openjdk/bin/java", "/usr/local/opt/openjdk/bin/java",
                 "/usr/local/Cellar/openjdk/22.0.2/libexec/openjdk.jdk/Contents/Home/bin/java"):
        # macOS ships a /usr/bin/java stub that only prints "Unable to locate a Java Runtime"; test-run each candidate
        if cand and Path(cand).exists():
            try:
                if sp.run([cand, "-version"], capture_output=True, timeout=20).returncode == 0:
                    return cand
            except Exception:
                pass
    return "java"


JAVA = _find_java()
SPECTRA_DIR = Path(os.environ.get("POLICY_CHECKER_SPECTRA_DIR", HERE / "vendor/spectra"))
CUDD_DIR = Path(os.environ.get("POLICY_CHECKER_CUDD_DIR", SPECTRA_DIR))   # libcudd.dylib / libcudd.so
CLASSPATH = f"{HERE / 'java/out'}:{SPECTRA_DIR / 'SpectraTool.jar'}:{SPECTRA_DIR / 'dependencies'}/*"

NOISE = re.compile(r"^(lookup, class|Could not load BDD|Using BDD Package|There are no core|extract strategy|rabin game not|getRabin)")


class SpectraError(RuntimeError):
    pass


def _run(cmd: str, spec: Path, timeout: int = 120) -> str:
    args = [JAVA, f"-Djava.library.path={CUDD_DIR}", "-cp", CLASSPATH, "SpecCheck", cmd, str(spec), str(timeout)]
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout + 30)
    except subprocess.TimeoutExpired:
        raise SpectraError(f"{cmd} timed out after {timeout}s")
    out = "\n".join(l for l in p.stdout.splitlines() if not NOISE.match(l))
    if p.returncode != 0 or out.startswith("ERROR"):
        err = out.split("\n", 1)[0] if out.startswith("ERROR") else p.stderr.strip().splitlines()[-1:] or ["unknown"]
        # Spectra's parser errors land in stderr; surface the first useful line.
        detail = [l for l in p.stderr.splitlines() if "rror" in l][:3]
        raise SpectraError(f"{cmd} failed: {err}\n" + "\n".join(detail))
    return out


def _result(out: str) -> str:
    m = re.search(r"^RESULT (.*)$", out, re.M)
    if not m:
        raise SpectraError(f"no RESULT line in output:\n{out[:500]}")
    return m.group(1).strip()


def check_realizable(spec: Path, timeout: int = 120) -> bool:
    return _result(_run("realizable", spec, timeout)) == "true"


def check_y_sat(spec: Path, timeout: int = 120) -> bool:
    """False means the guarantees are contradictory on their own - no assumption can repair it."""
    return _result(_run("ysat", spec, timeout)) == "true"


def unrealizable_core(spec: Path, timeout: int = 120) -> List[int]:
    """0-based line indices of guarantee expressions in a minimal unrealizable core."""
    r = _result(_run("core", spec, timeout))
    m = re.search(r"<\s*([^>]*)>", r)
    if not m:
        return []
    return [int(x) for x in m.group(1).split()]


@dataclass
class CSState:
    name: str
    values: Dict[str, bool]
    succ: List[str]
    initial: bool = False
    dead: bool = False


@dataclass
class CounterStrategy:
    states: Dict[str, CSState]
    raw: str = ""

    def initial(self) -> List[CSState]:
        return [s for s in self.states.values() if s.initial]

    def witness(self):
        """One concrete losing run.

        Spectra's counter-strategy states carry env *and* sys values. A "Dead" state is one where the
        controller's response already violates a guarantee. So a losing run is: a chain of live states
        (env move + a legal controller response) ending at a state whose successors are all dead, i.e.
        the environment has made a move to which every controller response violates some rule.

        Returns (path_of_live_states, final_env_values, dead_responses) where dead_responses are the
        losing successor states (each a distinct controller response to the same env move).
        """
        from collections import deque
        live_inits = [s for s in self.initial() if not s.dead]
        if not live_inits:
            # environment wins immediately: every initial response is losing
            deads = [s for s in self.initial() if s.dead]
            env_vals = deads[0].values if deads else {}
            return [], env_vals, deads
        for s0 in live_inits:
            prev = {s0.name: None}
            q = deque([s0.name])
            while q:
                n = q.popleft()
                st = self.states[n]
                succ = [self.states[m] for m in st.succ if m in self.states]
                dead = [x for x in succ if x.dead]
                live = [x for x in succ if not x.dead]
                if succ and not live:
                    return self._path(prev, n), dead[0].values, dead
                for x in live:
                    if x.name not in prev:
                        prev[x.name] = n
                        q.append(x.name)
        # no dead end reachable: the loss is a liveness violation (a cycle). Report the first live path.
        s0 = live_inits[0]
        return [s0], {}, []

    def _path(self, prev, n):
        out = []
        while n is not None:
            out.append(self.states[n])
            n = prev[n]
        return list(reversed(out))


STATE_RE = re.compile(r"(Initial )?(Dead )?State (\w+) <([^>]*)>\s*With (?:no successors\.|successors : ([^\n]*))")


def counter_strategy(spec: Path, timeout: int = 120) -> CounterStrategy:
    out = _run("cs", spec, timeout)
    body = out.split("RESULT_BEGIN", 1)[-1].split("RESULT_END", 1)[0]
    states: Dict[str, CSState] = {}
    for m in STATE_RE.finditer(body):
        vals = {k: v == "true" for k, v in re.findall(r"(\w+):(\w+)", m.group(4))}
        succ = [s.strip() for s in (m.group(5) or "").split(",") if s.strip()]
        states[m.group(3)] = CSState(m.group(3), vals, succ, initial=bool(m.group(1)), dead=bool(m.group(2)))
    return CounterStrategy(states, body.strip())


def _fmt(values: Dict[str, bool], names: List[str]) -> str:
    t = [v for v in names if values.get(v)]
    f = [v for v in names if v in values and not values[v]]
    return (", ".join(t) or "(nothing)") + (f"    [not: {', '.join(f)}]" if f else "")


def explain_dead(dead: "CSState", prev: Optional["CSState"], constraints, sys_names=()) -> List[str]:
    """Which guarantees does this losing controller response violate? constraints: iterable of (rule_id, kind, expr).
    Spectra omits sys variables that are false from some states; treat missing sys values as False."""
    from .evaluate import parse, evaluate, uses_next
    if sys_names:
        dead = CSState(dead.name, {**{v: False for v in sys_names}, **dead.values}, dead.succ, dead.initial, dead.dead)
    hits = []
    for rid, kind, expr in constraints:
        if kind != "guarantee":
            continue
        try:
            e = parse(expr)
        except ValueError:
            continue
        if uses_next(e):
            if prev is None:
                continue
            v = evaluate(e, prev.values, dead.values)
        else:
            v = evaluate(e, dead.values)
        if v is False and rid not in hits:
            hits.append(rid)
    return hits


def render_trace(cs: CounterStrategy, env_names: List[str], sys_names: List[str], constraints=()) -> str:
    """Human-readable losing run, with the rule each losing response violates."""
    path, env_vals, deads = cs.witness()
    lines = []
    for i, st in enumerate(path):
        lines.append(f"step {i}:  environment: {_fmt(st.values, env_names)}")
        lines.append(f"         controller:  {_fmt(st.values, sys_names)}")
    if deads:
        i = len(path)
        lines.append(f"step {i}:  environment: {_fmt(env_vals, env_names)}")
        lines.append(f"         controller:  no response satisfies every rule:")
        prev = path[-1] if path else None
        for d in deads:
            why = explain_dead(d, prev, constraints, sys_names)
            lines.append(f"             {_fmt(d.values, sys_names):40s} violates {', '.join(why) if why else '?'}")
        # responses that are not even listed were ruled out by a transition rule from the previous step
        listed = {tuple(d.values.get(v) for v in sys_names) for d in deads}
        if prev is not None:
            from itertools import product
            missing = []
            for combo in product([False, True], repeat=len(sys_names)):
                if combo in listed:
                    continue
                vals = dict(zip(sys_names, combo))
                fake = CSState("_", {**env_vals, **vals}, [])
                why = explain_dead(fake, prev, constraints, sys_names)
                if why:
                    missing.append((vals, why))
            for vals, why in missing:
                lines.append(f"             {_fmt(vals, sys_names):40s} violates {', '.join(why)}")
    elif path:
        lines.append("         (no dead end found - the environment wins by starving a liveness rule; see the raw counter-strategy)")
    return "\n".join(lines)

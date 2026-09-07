# policy-checker

Natural-language control policies for AI agents → GR(1) (Spectra) → **is the policy set jointly realisable?**
If not: the minimal conflicting core, and a concrete run the environment can force in which every controller
response violates a rule.

The question it answers is not "can this go wrong" (model checking) but "does a control strategy exist that
enforces every rule *whatever the agent does*" (realisability). The environment - the agent under control,
the user, the monitor, resource state - is adversarial; the system is the control layer.

```
$ python -m policy_checker check policies/email_agent.yaml --no-llm

# email_agent  (manual, 5 rules)
UNREALISABLE  (1.4s)
conflicting rules (minimal core): G1, G2, G3, G4
counter-trace - a run the environment can force:
step 0:  environment: req_send, refund_open    [not: user_confirm]
         controller:  escalate
step 1:  environment: req_send, refund_open    [not: user_confirm]
         controller:  no response satisfies every rule:
             (nothing)        violates G1
             block            violates G4
             allow            violates G2
             escalate         violates G3
             ...
```

Four sensible rules - resolve every request; no send without confirmation; don't escalate twice in a row;
never block while a refund is open - and an agent that proposes an unconfirmed send two steps running while a
refund is open leaves the controller with no legal move.

## Pipeline

1. `policies/*.yaml` - a policy set: env variables (what the agent/world does), sys variables (the controller's
   decisions), rules in English. Optional `spectra:` per rule for a hand-written reference encoding.
2. `policy_checker/translate.py` - Claude (`claude-opus-5`, structured output) translates each rule into one or
   more Spectra constraints, classified as assumption (about the environment) or guarantee (about the controller).
   Static validation (unknown variables, `next()` of sys vars in assumptions, missing rules) is fed back once.
3. `policy_checker/spectra.py` - drives Spectra's `SpectraTool` through a 40-line Java shim (`java/SpecCheck.java`):
   realisability, Y-satisfiability, unrealizable core, minimised counter-strategy.
4. `policy_checker/evaluate.py` - evaluates the emitted constraints on the counter-strategy's states so the
   trace says *which rule* each losing controller response violates.
5. `policy_checker/repair.py` - runs the interpolation-based assumption-refinement engine (MSc thesis,
   `~/Documents/interpolation-repair`), which proposes the environment assumption that restores realisability:
   ```
   minimal repair - add this assumption about the environment and every rule becomes enforceable  (2.4s):
       assumption G(!(!user_confirm & req_send & refund_open));
   ```
   The engine's interpolator is MathSAT 4, a Linux-only binary. On macOS its hardcoded path now resolves to a
   Python stand-in (`MathSAT4/.../bin/mathsat`) that computes a Craig interpolant on a BDD - the strongest
   interpolant (existential projection of the A-side) weakened by greedily dropping literals while I & B stays
   unsat. Same contract, same file formats; the engine code is untouched. Interpolants differ from MathSAT's, so
   the *particular* repair found can differ from the thesis runs.

## Run

```
python -m policy_checker check policies/email_agent.yaml            # Claude translation, then check
python -m policy_checker check policies/email_agent.yaml --no-llm   # hand-written encodings
python -m policy_checker batch policies/ [--no-llm] [--json]        # every set + conflict-rate summary
python -m policy_checker batch policies/ --no-llm --repair          # ... and run the repair engine on the conflicts
```
Outputs go to `out/`: the `.spectra` file, the translation JSON, the raw counter-strategy, `results.json`.

Translation backends, picked from the environment: `ANTHROPIC_API_KEY` (Claude), `GEMINI_API_KEY` (Gemini,
free tier is enough - default model `gemini-3.5-flash`), or `GOOGLE_CLOUD_PROJECT` + `gcloud auth application-default
login` (Claude on Vertex AI). Force one with `POLICY_CHECKER_PROVIDER=anthropic|gemini|vertex`.
Keep keys in `~/.config/policy-checker/env` and `source` it.

## Requirements

- JDK 22 (`/usr/local/Cellar/openjdk/22.0.2`), Spectra jars in `~/Documents/interpolation-repair/interpolation-repair/spectra`,
  and `libcudd.dylib` in `~/amba-fix` (built from `spectra-src-code/spectra-cudd` for macOS x86-64; without it
  Spectra falls back to a pure-Java BDD engine ~50× slower and the core/counter-strategy calls fail).
  Override paths with `POLICY_CHECKER_JAVA`, `POLICY_CHECKER_SPECTRA_DIR`, `POLICY_CHECKER_CUDD_DIR`.
- Python 3.12 with `anthropic`, `pydantic`, `pyyaml`.
- Build the shim once:
  `javac -cp "$SPECTRA/SpectraTool.jar:$SPECTRA/dependencies/*" -d java/out java/SpecCheck.java`

## Spectra subset

Booleans only. Initial constraints (plain expression), safety `G (...)` with `next(v)`, justice `GF (...)`.
Assumptions may not use `next()` of a sys variable. No bounded-time operators and no auxiliary variables:
rules that need them are encoded to the nearest GR(1) meaning and flagged `approximate`.

## Status

- Manual path, check + explain + repair: works end to end on the three example sets on macOS
  (2 of 3 unrealisable by design; both repaired in ~2.4s each).
- LLM path (Gemini 3.5 Flash, 7 Sep 2026): all 15 rules translated on the first attempt with no validator
  feedback; all three sets reach the same verdict and the same minimal core as the hand-written encodings;
  the two conflicts repair to the same assumptions. 3 of 3 agreement. `results.json` holds the run.
- Claude backends are implemented but have not been exercised (no key).

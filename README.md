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
5. `policy_checker/repair.py` - hook into the interpolation-based assumption-refinement engine (MSc thesis,
   `~/Documents/interpolation-repair`) that proposes the minimal environment assumption restoring realisability.
   Needs MathSAT 4 (Linux binary); reported as unavailable on macOS rather than faked.

## Run

```
python -m policy_checker check policies/email_agent.yaml            # Claude translation, then check
python -m policy_checker check policies/email_agent.yaml --no-llm   # hand-written encodings
python -m policy_checker batch policies/ [--no-llm] [--json]        # every set + conflict-rate summary
```
Outputs go to `out/`: the `.spectra` file, the translation JSON, the raw counter-strategy, `results.json`.

Translation needs `ANTHROPIC_API_KEY` in the environment (or `ant auth login`).

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

- Manual path: works end to end on the three example sets (2 of 3 unrealisable, by design).
- Claude path: implemented, awaiting an API key to run. The interesting measurement is translation fidelity:
  does the LLM encoding reach the same verdict and core as the hand-written one?
- Repair: the engine is wired but needs Linux/MathSAT.

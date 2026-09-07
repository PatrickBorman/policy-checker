#!/usr/bin/env bash
# One-time setup: compile the Java shim over the vendored Spectra jars. Run inside the conda env
# (conda env create -f environment.yml && conda activate policy-checker) or with any JDK >= 17 on PATH.
set -euo pipefail
cd "$(dirname "$0")"
# conda-forge's openjdk lives under $CONDA_PREFIX/lib/jvm; `conda activate` sets JAVA_HOME, but cover the case it didn't
[ -z "${JAVA_HOME:-}" ] && [ -n "${CONDA_PREFIX:-}" ] && [ -x "$CONDA_PREFIX/lib/jvm/bin/java" ] && export JAVA_HOME="$CONDA_PREFIX/lib/jvm"
[ -n "${JAVA_HOME:-}" ] && export PATH="$JAVA_HOME/bin:$PATH"
JAVAC="${JAVAC:-$(command -v javac || true)}"
[ -n "${JAVA_HOME:-}" ] && [ -x "$JAVA_HOME/bin/javac" ] && JAVAC="$JAVA_HOME/bin/javac"
# `dd` (BDD library used by the repair engine) ships as an sdist whose setup.py needs pkg_resources, which is
# absent from pip's isolated build env with setuptools >= 80. Install it without isolation.
PY="${PYTHON:-python}"
"$PY" -c "import dd" 2>/dev/null || "$PY" -m pip install --quiet --no-build-isolation dd
"$PY" -c "import jpype, dd, tarjan, numpy, pyparsing, yaml, pydantic" || { echo "python deps missing: see environment.yml"; exit 1; }
SP=vendor/spectra
mkdir -p java/out
if [ -n "$JAVAC" ]; then
  "$JAVAC" --release 17 -nowarn -cp "$SP/SpectraTool.jar:$SP/dependencies/*" -d java/out java/SpecCheck.java
else
  echo "no javac found; using the shipped java/out/SpecCheck.class (Java 17+ runtime needed)"
fi
command -v java >/dev/null || { echo "java not found: install a JRE >= 17 (conda env includes one) or set JAVA_HOME"; exit 1; }
[ -e engine/spectra ] || ln -s ../vendor/spectra engine/spectra
mkdir -p engine/temp engine/outputs out
echo "ok. try:  python -m policy_checker check policies/email_agent.yaml --no-llm --repair"

#!/usr/bin/env bash
# One-time setup: compile the Java shim over the vendored Spectra jars. Run inside the conda env
# (conda env create -f environment.yml && conda activate policy-checker) or with any JDK >= 17 on PATH.
set -euo pipefail
cd "$(dirname "$0")"
JAVAC="${JAVAC:-$(command -v javac || true)}"
[ -n "${JAVA_HOME:-}" ] && JAVAC="$JAVA_HOME/bin/javac"
[ -z "$JAVAC" ] && { echo "javac not found: install a JDK (conda env includes openjdk) or set JAVA_HOME"; exit 1; }
SP=vendor/spectra
mkdir -p java/out
"$JAVAC" -nowarn -cp "$SP/SpectraTool.jar:$SP/dependencies/*" -d java/out java/SpecCheck.java
[ -e engine/spectra ] || ln -s ../vendor/spectra engine/spectra
mkdir -p engine/temp engine/outputs out
echo "ok. try:  python -m policy_checker check policies/email_agent.yaml --no-llm --repair"

#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.tools:$PATH"
mkdir -p .runtime
export KUBECONFIG="$PWD/.runtime/kubeconfig"
export HELM_CACHE_HOME="$PWD/.runtime/helm/cache"
export HELM_CONFIG_HOME="$PWD/.runtime/helm/config"
export HELM_DATA_HOME="$PWD/.runtime/helm/data"
export MPLCONFIGDIR="$PWD/.runtime/matplotlib"
export NO_PROXY="localhost,127.0.0.1,::1"
if [ ! -x .venv/bin/python ]; then echo 'First run: bash scripts/install-tools.sh'; exit 1; fi
exec .venv/bin/python -m tools.lab "$@"

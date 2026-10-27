#!/usr/bin/env bash
# Install dependencies without changing package manifests or lockfiles.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
PIP_CACHE_DIR="${PIP_CACHE_DIR:-/tmp/smartestimate-pip}" .venv/bin/python -m pip install --require-hashes -r backend/requirements.lock
cd frontend
npm ci --cache "${npm_config_cache:-/tmp/smartestimate-npm}"

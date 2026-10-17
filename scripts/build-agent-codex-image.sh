#!/bin/bash
# Build the rehearse Codex CLI agent docker image.
#
# Usage:
#   bash scripts/build-agent-codex-image.sh [--no-cache] [tag]
#
# `--no-cache` rebuilds every layer, which also installs the current agent
# CLI release instead of reusing the one cached by an earlier build.
#
# Default tag is `rehearse-agent-codex:latest`.
set -euo pipefail

docker_build_options=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --no-cache) docker_build_options+=(--no-cache); shift ;;
    -*) echo "usage: $0 [--no-cache] [tag]" >&2; exit 2 ;;
    *) break ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAG="${1:-rehearse-agent-codex:latest}"

cd "${REPO_ROOT}"
exec docker build \
  "${docker_build_options[@]}" \
  -t "${TAG}" \
  -f docker/codex/Dockerfile \
  .

#!/bin/bash
# Build the rehearse Codex CLI agent docker image.
#
# Usage:
#   bash scripts/build-agent-codex-image.sh [tag]
#
# Default tag is `rehearse-agent-codex:latest`.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAG="${1:-rehearse-agent-codex:latest}"

cd "${REPO_ROOT}"
exec docker build \
  -t "${TAG}" \
  -f docker/codex/Dockerfile \
  .

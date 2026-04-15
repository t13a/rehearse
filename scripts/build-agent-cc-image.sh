#!/bin/bash
# Build the rehearse Claude Code agent docker image.
#
# Usage:
#   bash scripts/build-agent-cc-image.sh [tag]
#
# Default tag is `rehearse-agent-cc:latest`.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAG="${1:-rehearse-agent-cc:latest}"

cd "${REPO_ROOT}"
exec docker build \
  -t "${TAG}" \
  -f docker/claude-code/Dockerfile \
  .

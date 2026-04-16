#!/bin/bash
# Build the rehearse Claude Code agent docker image.
#
# Usage:
#   bash scripts/build-agent-claude-image.sh [tag]
#
# Default tag is `rehearse-agent-claude:latest`.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAG="${1:-rehearse-agent-claude:latest}"

cd "${REPO_ROOT}"
exec docker build \
  -t "${TAG}" \
  -f docker/claude/Dockerfile \
  .

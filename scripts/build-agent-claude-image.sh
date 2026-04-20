#!/bin/bash
# Build the rehearse Claude Code agent docker image.
#
# Usage:
#   bash scripts/build-agent-claude-image.sh [tag]
#
# Default tag is `rehearse-agent-claude:latest`.
#
# NOTE: This image installs Anthropic's proprietary Claude Code software.
# Built images are intended for local use only. Do not redistribute them
# unless Anthropic's license terms allow it.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAG="${1:-rehearse-agent-claude:latest}"

cd "${REPO_ROOT}"
echo "NOTE: The Claude Code agent image is for local use only; do not redistribute built images unless Anthropic's license terms allow it." >&2
sleep 10
exec docker build \
  -t "${TAG}" \
  -f docker/claude/Dockerfile \
  .

#!/bin/bash
# Build the rehearse Claude Code agent docker image.
#
# Usage:
#   bash scripts/build-agent-claude-image.sh [--no-cache] [tag]
#
# `--no-cache` rebuilds every layer, which also installs the current agent
# CLI release instead of reusing the one cached by an earlier build.
#
# Default tag is `rehearse-agent-claude:latest`.
#
# NOTE: This image installs Anthropic's proprietary Claude Code software.
# Built images are intended for local use only. Do not redistribute them
# unless Anthropic's license terms allow it.
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
TAG="${1:-rehearse-agent-claude:latest}"

cd "${REPO_ROOT}"
echo "NOTE: The Claude Code agent image is for local use only; do not redistribute built images unless Anthropic's license terms allow it." >&2
sleep 10
exec docker build \
  "${docker_build_options[@]}" \
  -t "${TAG}" \
  -f docker/claude/Dockerfile \
  .

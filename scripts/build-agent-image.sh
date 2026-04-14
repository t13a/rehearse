#!/bin/bash
# Build the rehearse-agent docker image.
#
# Usage:
#   bash scripts/build-agent-image.sh [tag]
#
# Default tag is `rehearse-agent:latest` (matches profile agent_image default).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAG="${1:-rehearse-agent:latest}"

cd "${REPO_ROOT}"
exec docker build \
  -t "${TAG}" \
  -f docker/agent/Dockerfile \
  .

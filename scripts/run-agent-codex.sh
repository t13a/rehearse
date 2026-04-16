#!/bin/bash
# rehearse agent runner for Codex CLI.
#
# Contract: the harness exports REHEARSE_SESSION_* / REHEARSE_AGENT_* into the
# environment, then exec's this script. The script assembles the docker
# invocation and lets the container's exit code propagate as its own.
set -euo pipefail

: "${REHEARSE_SESSION_WORKSPACE:?required}"
: "${REHEARSE_SESSION_DATA:?required}"
: "${REHEARSE_SESSION_HOME:?required}"
: "${REHEARSE_SESSION_RUN_LOCK:?required}"
: "${REHEARSE_SESSION_A:?required}"
: "${REHEARSE_SESSION_B:?required}"
: "${REHEARSE_AGENT_IMAGE:?required}"
: "${REHEARSE_AGENT_UID:?required}"
: "${REHEARSE_AGENT_GID:?required}"
: "${REHEARSE_AGENT_TIMEOUT:?required}"

args=(
  docker run --rm
  --user "${REHEARSE_AGENT_UID}:${REHEARSE_AGENT_GID}"
  -v "${REHEARSE_SESSION_DATA}:${REHEARSE_SESSION_DATA}:rw"
  -v "${REHEARSE_SESSION_HOME}:/home/agent:rw"
  -v "${REHEARSE_SESSION_A}:${REHEARSE_SESSION_A}:ro"
  -v "${REHEARSE_SESSION_B}:${REHEARSE_SESSION_B}:ro"
  -w "${REHEARSE_SESSION_DATA}"
  -e "HOME=/home/agent"
  -e "CODEX_HOME=/home/agent/.codex"
  -e "REHEARSE_WORKSPACE_DATA=${REHEARSE_SESSION_DATA}"
  -e "REHEARSE_AGENT_TIMEOUT=${REHEARSE_AGENT_TIMEOUT}"
)

if [ -n "${REHEARSE_AGENT_MESSAGE:-}" ]; then
  args+=(-e "REHEARSE_AGENT_MESSAGE=${REHEARSE_AGENT_MESSAGE}")
fi

if [ -n "${REHEARSE_AGENT_EXTRA_ARGS:-}" ]; then
  args+=(-e "REHEARSE_AGENT_EXTRA_ARGS=${REHEARSE_AGENT_EXTRA_ARGS}")
fi

args+=("${REHEARSE_AGENT_IMAGE}")

exec flock -F -E 75 -n "${REHEARSE_SESSION_RUN_LOCK}" "${args[@]}"

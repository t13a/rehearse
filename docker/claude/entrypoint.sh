#!/bin/bash
# Container entrypoint for the rehearse Claude Code agent.
#
# Run inside the container by `scripts/docker-runner.sh`. Reads its
# parameters from the environment, then exec's `claude` under `timeout`.
set -euo pipefail

agent_init="$HOME/.rehearse/agent/init.sh"
if [ -f "${agent_init}" ]; then
  # shellcheck source=/dev/null
  . "${agent_init}"
fi

cd "${REHEARSE_WORKSPACE_DATA:-/workspace/data}"

args=(
  --print
  --permission-mode bypassPermissions
)

if ls "$HOME/.claude/projects/"*/*.jsonl >/dev/null 2>&1; then
  args+=(--continue)
  prompt="${REHEARSE_AGENT_MESSAGE:-作業を再開してください。}"
else
  prompt="${REHEARSE_AGENT_MESSAGE:-作業を開始してください。}"
fi

if [ -n "${REHEARSE_AGENT_EXTRA_ARGS:-}" ]; then
  # Word-split intentionally: caller passes space-separated flags.
  # shellcheck disable=SC2206
  args+=(${REHEARSE_AGENT_EXTRA_ARGS})
fi

TIMEOUT="${REHEARSE_AGENT_TIMEOUT:-3600}"

# `timeout` returns 124 on SIGTERM and 137 on SIGKILL; the harness keys off
# both to recognize a timeout.
exec timeout --kill-after=10 "${TIMEOUT}" \
  claude "${args[@]}" \
  "$prompt"

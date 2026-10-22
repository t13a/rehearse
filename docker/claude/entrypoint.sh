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

cd "${REHEARSE_AGENT_WORK_DIR:-/mnt}"

args=(
  --print
  --permission-mode bypassPermissions
)

# Every run starts a new session. The state of the work lives in the work
# directory, and resuming would resend the whole earlier conversation.
prompt="${REHEARSE_AGENT_MESSAGE:-Start working.}"

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

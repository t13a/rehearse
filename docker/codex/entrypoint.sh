#!/bin/bash
# Container entrypoint for the rehearse Codex CLI agent.
#
# Run inside the container by `scripts/docker-runner.sh`. Reads its
# parameters from the environment, then runs `codex exec` under `timeout`.
set -euo pipefail

agent_init="$HOME/.rehearse/agent/init.sh"
if [ -f "${agent_init}" ]; then
  # shellcheck source=/dev/null
  . "${agent_init}"
fi

cd "${REHEARSE_AGENT_WORK_DIR:-/mnt}"

global_args=(
  --yolo
)

if [ -n "${REHEARSE_AGENT_EXTRA_ARGS:-}" ]; then
  # Word-split intentionally: caller passes space-separated flags.
  # shellcheck disable=SC2206
  global_args+=(${REHEARSE_AGENT_EXTRA_ARGS})
fi

TIMEOUT="${REHEARSE_AGENT_TIMEOUT:-3600}"

if find "${CODEX_HOME:-$HOME/.codex}/sessions" -type f -name "*.jsonl" -print -quit 2>/dev/null | grep -q .; then
  command=(codex "${global_args[@]}" exec resume --last --skip-git-repo-check)
  prompt="${REHEARSE_AGENT_MESSAGE:-作業を再開してください。}"
else
  command=(codex "${global_args[@]}" exec --skip-git-repo-check)
  prompt="${REHEARSE_AGENT_MESSAGE:-作業を開始してください。}"
fi

# `timeout` returns 124 on SIGTERM and 137 on SIGKILL; the harness keys off
# both to recognize a timeout.
exec timeout --kill-after=10 "${TIMEOUT}" "${command[@]}" "${prompt}"

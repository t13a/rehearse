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

cd "${REHEARSE_WORKSPACE_DATA:-/workspace/data}"

global_args=(
  --ask-for-approval never
)

exec_args=(
  --sandbox danger-full-access
  --skip-git-repo-check
)

if [ -n "${REHEARSE_AGENT_EXTRA_ARGS:-}" ]; then
  # Word-split intentionally: caller passes space-separated flags.
  # shellcheck disable=SC2206
  exec_args+=(${REHEARSE_AGENT_EXTRA_ARGS})
fi

prompt_path="${REHEARSE_AGENT_PROMPT_PATH:-/opt/rehearse/prompts/agent.md}"
system_prompt="$(cat "${prompt_path}")"
user_prompt="${REHEARSE_AGENT_MESSAGE:-作業を開始してください。仕様は上記の指示にあります。}"
prompt="${system_prompt}"$'\n\n'"${user_prompt}"

TIMEOUT="${REHEARSE_AGENT_TIMEOUT:-3600}"

if find "${CODEX_HOME:-$HOME/.codex}/sessions" -type f -name "*.jsonl" -print -quit 2>/dev/null | grep -q .; then
  command=(codex "${global_args[@]}" exec resume --last --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check -)
else
  command=(codex "${global_args[@]}" exec "${exec_args[@]}" --color never -)
fi

# `timeout` returns 124 on SIGTERM and 137 on SIGKILL; the harness keys off
# both to recognize a timeout.
printf '%s\n' "${prompt}" | timeout --kill-after=10 "${TIMEOUT}" "${command[@]}"

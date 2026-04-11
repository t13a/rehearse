#!/bin/bash
# Container entrypoint for the rehearse Claude Code agent.
#
# Run inside the container by `scripts/run-agent-cc.sh`. Reads its
# parameters from the environment, then exec's `claude` under `timeout`.
set -euo pipefail

: "${ANTHROPIC_API_KEY:?ANTHROPIC_API_KEY must be set}"

cd "${REHEARSE_WORKSPACE_DATA:-/workspace/data}"

args=(
  --print
  --permission-mode bypassPermissions
  --append-system-prompt "$(cat /opt/rehearse/prompts/agent.md)"
)

if [ -n "${REHEARSE_MCP_CONFIG_PATH:-}" ] && [ -f "${REHEARSE_MCP_CONFIG_PATH}" ]; then
  args+=(--mcp-config "${REHEARSE_MCP_CONFIG_PATH}")
fi

TIMEOUT="${REHEARSE_AGENT_TIMEOUT:-3600}"

# `timeout` returns 124 on SIGTERM and 137 on SIGKILL; the harness keys off
# both to recognize a timeout.
exec timeout --kill-after=10 "${TIMEOUT}" \
  claude "${args[@]}" \
  "作業を開始してください。仕様はシステムプロンプト (/opt/rehearse/prompts/agent.md) にあります。"

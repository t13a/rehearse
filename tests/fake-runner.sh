#!/bin/bash
# Drop-in replacement for scripts/run-agent-cc.sh used by the test suite.
# Reproduces the Step 2 placeholder behavior with busybox: ls inbox/ and archive/, then
# touch archive/.done. No API key, no rehearse-agent image.
set -euo pipefail

: "${REHEARSE_SESSION_DATA:?required}"
: "${REHEARSE_AGENT_UID:?required}"
: "${REHEARSE_AGENT_GID:?required}"
: "${REHEARSE_AGENT_IMAGE:?required}"

exec docker run --rm \
  --user "${REHEARSE_AGENT_UID}:${REHEARSE_AGENT_GID}" \
  -v "${REHEARSE_SESSION_DATA}:${REHEARSE_SESSION_DATA}:rw" \
  -w "${REHEARSE_SESSION_DATA}" \
  "${REHEARSE_AGENT_IMAGE}" \
  sh -c 'ls inbox/ && ls archive/ && touch archive/.done'

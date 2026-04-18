#!/bin/bash
# Drop-in replacement for agent runner scripts used by the test suite.
# Reproduces the Step 2 placeholder behavior with busybox: ls inbox/ and outbox/, then
# touch outbox/.done. No API key, no real agent image.
set -euo pipefail

: "${REHEARSE_SESSION_DATA:?required}"
: "${REHEARSE_SESSION_RUN_LOCK:?required}"
: "${REHEARSE_AGENT_UID:?required}"
: "${REHEARSE_AGENT_GID:?required}"
: "${REHEARSE_AGENT_IMAGE:?required}"

message_env=()
if [[ -v REHEARSE_AGENT_MESSAGE ]]; then
  message_env=(-e REHEARSE_AGENT_MESSAGE)
fi

exec flock -F -E 75 -n "${REHEARSE_SESSION_RUN_LOCK}" docker run --rm \
  --user "${REHEARSE_AGENT_UID}:${REHEARSE_AGENT_GID}" \
  "${message_env[@]}" \
  -v "${REHEARSE_SESSION_DATA}:${REHEARSE_SESSION_DATA}:rw" \
  -w "${REHEARSE_SESSION_DATA}" \
  "${REHEARSE_AGENT_IMAGE}" \
  sh -c 'ls inbox/ && ls outbox/ && if [ "${REHEARSE_AGENT_MESSAGE+x}" = x ]; then printf "%s\n" "$REHEARSE_AGENT_MESSAGE" > outbox/FYI.md; fi && touch outbox/.done'

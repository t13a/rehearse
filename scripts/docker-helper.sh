#!/bin/bash
# rehearse Docker helper for root-owned maintenance tasks.
#
# Contract: the harness exports REHEARSE_HELPER_* and passes the command to run
# inside the helper image. The helper mounts a broad parent directory so cleanup
# can remove mount children and chown can address session paths by host path.
set -euo pipefail

: "${REHEARSE_HELPER_IMAGE:?required}"
: "${REHEARSE_HELPER_MOUNT:?required}"

if [ "$#" -lt 1 ]; then
  echo "usage: docker-helper.sh CMD [ARGS...]" >&2
  exit 2
fi

exec docker run --rm \
  --user 0:0 \
  -v "${REHEARSE_HELPER_MOUNT}:${REHEARSE_HELPER_MOUNT}:rw" \
  "${REHEARSE_HELPER_IMAGE}" \
  "$@"

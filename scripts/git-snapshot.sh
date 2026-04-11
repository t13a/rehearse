#!/bin/bash
set -euo pipefail

# Initialize a git repo at the session directory and take the initial snapshot.
# Only the data/ tree is tracked; everything else is ignored.

if [ $# -ne 1 ]; then
    echo "usage: $0 <session_dir>" >&2
    exit 2
fi

cd "$1"
git init -q
cat > .gitignore <<'EOF'
/*
!/.gitignore
!/data
EOF
git add -A
git -c user.email=rehearse@localhost -c user.name=rehearse \
    commit -q -m "session start"

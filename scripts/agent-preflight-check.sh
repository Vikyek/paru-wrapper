#!/usr/bin/env bash
set -euo pipefail

echo "==> Running paru-wrapper pre-flight checks..."

# 1. Check syntax of bash scripts
echo "[1/3] Validating bash syntax..."
bash -n paru-wrapper

# 2. Verify wrapper argument forwarding logic
echo "[2/3] Checking wrapper argument forwarding invariants..."
if grep -E '/usr/bin/paru.*-- "\$@"' paru-wrapper >/dev/null 2>&1; then
    echo "ERROR: Invalid '-- \"\$@\"' pattern found in paru-wrapper. User flags will break!" >&2
    exit 1
fi

# 3. Check git status clean check recommendation
echo "[3/3] Checking workspace state..."
if [ -n "$(git status --porcelain)" ]; then
    echo "NOTICE: Workspace has uncommitted changes:"
    git status --short
else
    echo "Workspace clean."
fi

echo "==> Pre-flight check PASSED."

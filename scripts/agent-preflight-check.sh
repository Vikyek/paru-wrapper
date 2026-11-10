#!/usr/bin/env bash
set -euo pipefail

echo "==> Running paru-wrapper pre-flight checks..."

# 1. Check syntax of bash scripts
echo "[1/4] Validating bash syntax..."
bash -n paru-wrapper
bash -n pacman-wrapper
bash -n paru-wrapper-gittinator
bash -n default-plugins/*.sh

# 2. Verify wrapper argument forwarding logic
echo "[2/4] Checking wrapper argument forwarding invariants..."
if grep -E '/usr/bin/paru.*-- "\$@"' paru-wrapper >/dev/null 2>&1; then
    echo "ERROR: Invalid '-- \"\$@\"' pattern found in paru-wrapper. User flags will break!" >&2
    exit 1
fi

# 3. Verify CLI entrypoint parity
echo "[3/4] Verifying CLI entrypoints (--wrapper-help, --wrapper-version)..."
./paru-wrapper --wrapper-help >/dev/null
./paru-wrapper --wrapper-version >/dev/null

# 4. Check git status clean check recommendation
echo "[4/4] Checking workspace state..."
if [ -n "$(git status --porcelain)" ]; then
    echo "NOTICE: Workspace has uncommitted changes:"
    git status --short
else
    echo "Workspace clean."
fi

echo "==> Pre-flight check PASSED."

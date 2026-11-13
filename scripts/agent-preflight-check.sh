#!/usr/bin/env bash
set -euo pipefail

echo "==> Running paru-wrapper pre-flight checks..."

# 1. Check syntax of bash scripts
echo "[1/5] Validating bash syntax..."
bash -n paru-wrapper
bash -n pacman-wrapper
bash -n paru-wrapper-gittinator
bash -n default-plugins/*.sh

# 2. Verify wrapper argument forwarding logic
echo "[2/5] Checking wrapper argument forwarding invariants..."
if grep -E '/usr/bin/paru.*-- "\$@"' paru-wrapper >/dev/null 2>&1; then
    echo "ERROR: Invalid '-- \"\$@\"' pattern found in paru-wrapper. User flags will break!" >&2
    exit 1
fi

# 3. Verify CLI entrypoint parity & doc/metadata sync
echo "[3/5] Verifying CLI entrypoints (--wrapper-help, --wrapper-version)..."
help_out=$(./paru-wrapper --wrapper-help)
./paru-wrapper --wrapper-version >/dev/null

echo "[4/5] Checking .SRCINFO and plugin documentation parity..."
if command -v makepkg >/dev/null 2>&1; then
    if ! diff -u .SRCINFO <(makepkg --printsrcinfo) >/dev/null 2>&1; then
        echo "ERROR: .SRCINFO is out of sync with PKGBUILD. Run: makepkg --printsrcinfo > .SRCINFO" >&2
        exit 1
    fi
fi

for plugin in default-plugins/*.sh; do
    p_base=$(basename "$plugin")
    for doc in README.md man1/paru-wrapper.1; do
        if ! grep -Fq "$p_base" "$doc"; then
            echo "ERROR: Plugin '$p_base' missing from $doc" >&2
            exit 1
        fi
    done
    if ! printf '%s\n' "$help_out" | grep -Fq "$p_base"; then
        echo "ERROR: Plugin '$p_base' missing from --wrapper-help" >&2
        exit 1
    fi
done

# 5. Check git status clean check recommendation
echo "[5/5] Checking workspace state..."
if [ -n "$(git status --porcelain)" ]; then
    echo "NOTICE: Workspace has uncommitted changes:"
    git status --short
    changed_code=$(git status --porcelain | awk '{print $2}' | grep -E '^(paru-wrapper|pacman-wrapper|paru-wrapper-gittinator|update_mkvpkg_aur\.py|default-plugins/)' || true)
    changed_docs=$(git status --porcelain | awk '{print $2}' | grep -E '^(README\.md|man1/paru-wrapper\.1)$' || true)
    if [ -n "$changed_code" ] && [ -z "$changed_docs" ]; then
        echo "WARNING: Code/plugin files changed without README.md or man1/paru-wrapper.1 updates. Verify doc sync." >&2
    fi
else
    echo "Workspace clean."
fi

echo "==> Pre-flight check PASSED."

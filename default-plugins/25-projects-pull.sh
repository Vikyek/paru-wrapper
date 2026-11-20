#!/bin/bash
# Plugin: Projects-Pull integration for paru-wrapper
# Automatically pulls fast-forward updates for git repositories in Projects directory
# during pre-transaction phase and rebuilds/installs updated installed packages.

plugin_name="projects-pull"

plugin_check() {
    local invoking_user="${SUDO_USER:-$USER}"
    local user_home
    user_home=$(getent passwd "$invoking_user" 2>/dev/null | cut -d: -f6)
    local proj_dir="${PARU_WRAPPER_PROJECTS_DIR:-${user_home}/Projects}"
    [ -d "$proj_dir" ]
}

plugin_hook() {
    local hook_event="$1"
    shift

    case "$hook_event" in
        pre-transaction)
            local invoking_user="${SUDO_USER:-$USER}"
            local user_home
            user_home=$(getent passwd "$invoking_user" 2>/dev/null | cut -d: -f6)
            local proj_dir="${PARU_WRAPPER_PROJECTS_DIR:-${user_home}/Projects}"

            [ -d "$proj_dir" ] || return 0

            msg_info "[projects-pull] Checking for upstream updates in ${proj_dir}..."

            run_as_user() {
                if [ "$(id -u)" -eq 0 ] && [ -n "${invoking_user:-}" ]; then
                    runuser -u "$invoking_user" -- "$@"
                else
                    "$@"
                fi
            }

            # Iterate over git repositories in projects directory
            for repo in "$proj_dir"/*; do
                [ -d "$repo/.git" ] || continue
                [ -f "$repo/PKGBUILD" ] || continue

                local repo_name
                repo_name=$(basename "$repo")

                # Check if repo has clean working tree and tracked remote
                local is_dirty
                is_dirty=$(git -C "$repo" status --porcelain 2>/dev/null)
                if [ -n "$is_dirty" ]; then
                    continue
                fi

                local remote_url
                remote_url=$(git -C "$repo" config --get remote.origin.url 2>/dev/null)
                [ -n "$remote_url" ] || continue

                if [ "${DRY_RUN:-false}" = true ]; then
                    msg_info "[projects-pull] DRY RUN: would pull and check ${repo_name}"
                    continue
                fi

                # Attempt fast-forward update as the invoking user
                local pull_output
                pull_output=$(run_as_user git -C "$repo" pull --ff-only 2>&1)
                local pull_exit=$?

                if [ $pull_exit -eq 0 ] && [ "$pull_output" != "Already up to date." ]; then
                    msg_info "[projects-pull] Updated ${repo_name}: ${pull_output}"

                    case "${PARU_WRAPPER_AUTO_UPDATE_INSTALLED:-true}" in
                        true|1|yes|on|TRUE|YES|ON) ;;
                        *) continue ;;
                    esac

                    local pkgnames is_pkg_installed=false
                    pkgnames=$(python3 - "$repo/PKGBUILD" "$repo/.SRCINFO" << 'PYPKG' 2>/dev/null || true
import os, re, shlex, sys
pb, srcinfo = sys.argv[1], sys.argv[2]
names = []
if os.path.isfile(pb):
    with open(pb, "r", errors="replace") as f:
        text = f.read()
    lines = [ln.split("#", 1)[0] if not ln.lstrip().startswith("#") else "" for ln in text.splitlines()]
    clean = "\n".join(lines)
    m_arr = re.search(r'(?m)^\s*pkgname\s*=\s*\((.*?)\)', clean, re.S)
    if m_arr:
        try:
            names = shlex.split(m_arr.group(1))
        except ValueError:
            names = m_arr.group(1).split()
    else:
        m_str = re.search(r'(?m)^\s*pkgname\s*=\s*([^\n]+)', clean)
        if m_str:
            val = m_str.group(1).strip().strip("'\"")
            if val and "$" not in val:
                names = [val]
if (not names or any("$" in n for n in names)) and os.path.isfile(srcinfo):
    with open(srcinfo, "r", errors="replace") as f:
        si_names = []
        for ln in f:
            m = re.match(r'^\s*pkgname\s*=\s*(\S+)', ln)
            if m:
                si_names.append(m.group(1))
        if si_names:
            names = si_names
for n in names:
    n = n.strip("'\"")
    if n and "$" not in n:
        print(n)
PYPKG
)
                    if [ -z "$pkgnames" ]; then
                        pkgnames="$repo_name"
                    fi
                    for p in $pkgnames; do
                        if pacman -Qq "$p" >/dev/null 2>&1; then
                            is_pkg_installed=true
                            break
                        fi
                    done

                    if [ "$is_pkg_installed" = true ]; then
                        if command -v verify_pkg >/dev/null 2>&1; then
                            local verify_json verify_danger=0 verify_verdict="" verify_rc=0
                            verify_json=$(verify_pkg --json "$repo" 2>/dev/null) || verify_rc=$?
                            if [ -n "$verify_json" ]; then
                                verify_danger=$(printf '%s' "$verify_json" | jq -r '.danger_score // 0' 2>/dev/null || echo 0)
                                verify_verdict=$(printf '%s' "$verify_json" | jq -r '.verdict // ""' 2>/dev/null || echo "")
                            fi
                            if [ "$verify_rc" -ne 0 ] || [ "${verify_danger:-0}" -gt 0 ] || [ "$verify_verdict" = "SUSPICIOUS" ] || [ "$verify_verdict" = "CRITICAL_RISK" ]; then
                                verify_pkg "$repo" >&2 || true
                                msg_warn "[projects-pull] Security check flagged '${repo_name}' (Danger: ${verify_danger}). Skipping automatic makepkg -sfi --noconfirm."
                                msg_warn "[projects-pull] Inspect upstream changes manually: git -C '${repo}' diff ORIG_HEAD..HEAD"
                                continue
                            fi
                        fi
                        msg_info "[projects-pull] Rebuilding and installing updated project '${repo_name}'..."
                        if run_as_user bash -c 'cd "$1" && makepkg -sfi --noconfirm' _ "$repo"; then
                            if declare -F dispatch_plugin_hooks >/dev/null; then
                                dispatch_plugin_hooks package-rebuilt "$repo_name"
                            fi
                        else
                            msg_warn "[projects-pull] Failed to rebuild/install ${repo_name}"
                        fi
                    fi
                fi
            done
            ;;
    esac
}

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
                    pkgnames=$(bash -c 'source "$1" >/dev/null 2>&1 && printf "%s\n" "${pkgname[@]}"' _ "$repo/PKGBUILD")
                    for p in $pkgnames; do
                        if pacman -Qq "$p" >/dev/null 2>&1; then
                            is_pkg_installed=true
                            break
                        fi
                    done

                    if [ "$is_pkg_installed" = true ]; then
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

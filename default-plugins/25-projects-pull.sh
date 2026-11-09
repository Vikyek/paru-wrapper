#!/bin/bash
# Plugin: Projects-Pull integration for paru-wrapper
# Automatically pulls fast-forward updates for git repositories in Projects directory
# during pre-transaction phase before local package evaluations or builds.

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

                # Attempt fast-forward update running as the invoking user
                local pull_output
                pull_output=$(runuser -u "$invoking_user" -- git -C "$repo" pull --ff-only 2>&1)
                local pull_exit=$?

                if [ $pull_exit -eq 0 ]; then
                    if [ "$pull_output" != "Already up to date." ]; then
                        msg_info "[projects-pull] Updated ${repo_name}: ${pull_output}"
                    fi
                fi
            done
            ;;
    esac
}

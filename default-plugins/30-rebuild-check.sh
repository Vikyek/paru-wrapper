#!/bin/bash
# Plugin: Rebuild-Check integration for paru-wrapper
# Runs deferred rebuild-check analysis after package upgrades.

plugin_name="rebuild-check"

plugin_check() {
    command -v rebuild-check >/dev/null 2>&1
}

plugin_hook() {
    local hook_event="$1"
    shift

    case "$hook_event" in
        deferred-hooks)
            if plugin_check; then
                if [ "${is_anneal:-false}" = true ] || [ "${REBUILD_CHECK_ACTIVE:-0}" = "1" ]; then
                    msg_info "[rebuild-check] Skipping deferred check while running inside anneal/rebuild-check."
                    return 0
                fi
                if [ "${DRY_RUN:-false}" = true ]; then
                    msg_info "DRY RUN: [rebuild-check] would analyze packages needing rebuild"
                else
                    msg_info "[rebuild-check] Checking for packages requiring rebuild..."
                    if [ "$(id -u)" -eq 0 ]; then
                        if [ "$#" -gt 0 ]; then
                            printf '%s\n' "$@" | /usr/bin/rebuild-check || true
                        else
                            /usr/bin/rebuild-check || true
                        fi
                    else
                        if [ "$#" -gt 0 ]; then
                            printf '%s\n' "$@" | sudo /usr/bin/rebuild-check || true
                        else
                            sudo /usr/bin/rebuild-check || true
                        fi
                    fi
                fi
            fi
            ;;
    esac
}

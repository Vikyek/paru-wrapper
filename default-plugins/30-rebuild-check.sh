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
                if [ "${DRY_RUN:-false}" = true ]; then
                    msg_info "DRY RUN: [rebuild-check] would analyze packages needing rebuild"
                else
                    msg_info "[rebuild-check] Checking for packages requiring rebuild..."
                    if [ "$#" -gt 0 ]; then
                        printf '%s\n' "$@" | sudo /usr/bin/rebuild-check 2>/dev/null || true
                    else
                        sudo /usr/bin/rebuild-check 2>/dev/null || true
                    fi
                fi
            fi
            ;;
    esac
}

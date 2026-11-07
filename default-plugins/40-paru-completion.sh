#!/bin/bash
# Plugin: Paru-Completion integration for paru-wrapper
# Rebuilds paru completion cache after package additions/removals.

plugin_name="paru-completion"

plugin_check() {
    [ -x /usr/bin/paru-completion-update ]
}

plugin_hook() {
    local hook_event="$1"
    shift

    case "$hook_event" in
        deferred-hooks)
            if plugin_check; then
                if [ "${DRY_RUN:-false}" = true ]; then
                    msg_info "DRY RUN: [paru-completion] would update completion cache"
                else
                    msg_info "[paru-completion] Updating completion cache..."
                    sudo /usr/bin/paru-completion-update 2>/dev/null || true
                fi
            fi
            ;;
    esac
}

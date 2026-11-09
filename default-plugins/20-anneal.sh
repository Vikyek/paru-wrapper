#!/bin/bash
# Plugin: Anneal integration for paru-wrapper
# Handles unmarking rebuilt packages from the anneal queue.

plugin_name="anneal"

plugin_check() {
    command -v anneal >/dev/null 2>&1
}

plugin_hook() {
    local hook_event="$1"
    shift

    case "$hook_event" in
        package-rebuilt)
            local pkg="$1"
            if plugin_check; then
                msg_info "[anneal] Unmarking '$pkg' in rebuild queue..."
                sudo anneal unmark "$pkg" 2>/dev/null || true
            fi
            ;;
    esac
}

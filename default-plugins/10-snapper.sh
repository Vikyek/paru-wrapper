#!/bin/bash
# Plugin: Snapper integration for paru-wrapper
# Handles pre/post transaction btrfs filesystem snapshots.

plugin_name="snapper"

plugin_check() {
    command -v snapper >/dev/null 2>&1
}

plugin_hook() {
    local hook_event="$1"
    shift

    case "$hook_event" in
        pre-transaction)
            if [ "${hooks_disabled:-false}" = true ] && plugin_check; then
                if [ "${DRY_RUN:-false}" = true ]; then
                    msg_info "DRY RUN: [snapper] would take pre-transaction snapshot"
                    PRE_SNAP_ID=""
                else
                    PRE_SNAP_ID=$(sudo snapper -c root create -d "paru-wrapper pre-transaction" -t pre -p 2>/dev/null || true)
                    export PRE_SNAP_ID
                    if [ -n "$PRE_SNAP_ID" ]; then
                        msg_info "[snapper] Created pre-transaction snapshot #$PRE_SNAP_ID"
                    fi
                fi
            fi
            ;;
        post-transaction)
            if [ "${hooks_disabled:-false}" = true ] && [[ -n "${PRE_SNAP_ID:-}" ]] && plugin_check; then
                if [ "${DRY_RUN:-false}" = true ]; then
                    msg_info "DRY RUN: [snapper] would take post-transaction snapshot for pre-snapshot #$PRE_SNAP_ID"
                else
                    msg_info "[snapper] Taking post-transaction snapshot for #$PRE_SNAP_ID..."
                    sudo snapper -c root create -d "paru-wrapper post-transaction" -t post --pre-number "$PRE_SNAP_ID" 2>/dev/null || true
                fi
            fi
            ;;
    esac
}

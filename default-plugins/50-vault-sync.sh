#!/bin/bash
# Plugin: Vault-Sync integration for paru-wrapper
# Triggers configuration vault sync pass in the background after transactions.

plugin_name="vault-sync"

plugin_check() {
    local invoking_user="${SUDO_USER:-$USER}"
    local user_home
    user_home=$(getent passwd "$invoking_user" 2>/dev/null | cut -d: -f6)
    [ -n "$user_home" ] && [ -f "${user_home}/.gemini/config/scripts/auto_sync_vault.py" ]
}

plugin_hook() {
    local hook_event="$1"
    shift

    case "$hook_event" in
        post-transaction-bg)
            local invoking_user="${SUDO_USER:-$USER}"
            local user_home
            user_home=$(getent passwd "$invoking_user" 2>/dev/null | cut -d: -f6)
            local sync_script="${user_home}/.gemini/config/scripts/auto_sync_vault.py"
            if [ -f "$sync_script" ]; then
                msg_info "[vault-sync] Triggering background configuration sync..."
                runuser -u "$invoking_user" -- python3 "$sync_script" >/dev/null 2>&1 &
            fi
            ;;
    esac
}

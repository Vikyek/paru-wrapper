## 2024-05-14 - Optimize is_installed
**Learning:** Checking package installation status one-by-one with `pacman -Qq <pkg>` in Python causes significant N+1 subprocess overhead in Arch Linux wrapper scripts.
**Action:** Always pre-fetch installed packages using a bulk `pacman -Qq` query, cache the results in a module-level Python `set`, and fall back to single queries only if the bulk query fails. This reduces complexity from O(N) subprocess forks to O(1) set lookups.

## 2024-05-14 - Optimize is_installed
**Learning:** Checking package installation status one-by-one with `pacman -Qq <pkg>` in Python causes significant N+1 subprocess overhead in Arch Linux wrapper scripts.
**Action:** Always pre-fetch installed packages using a bulk `pacman -Qq` query, cache the results in a module-level Python `set`, and fall back to single queries only if the bulk query fails. This reduces complexity from O(N) subprocess forks to O(1) set lookups.

## 2024-05-24 - Optimize vercmp subprocess overhead
**Learning:** Calling the CLI utility `vercmp` repeatedly in a loop (even when batched via `bash -c`) introduces extreme overhead from subprocess forks in Python scripts managing large package lists. Pure Python standard libraries cannot replace it because PEP 440 sorts Arch versions incorrectly (e.g. `1.0a` is newer than `1.0` in PEP 440, but older in Pacman).
**Action:** Implemented a pure Python port of Pacman's internal `alpm_pkg_vercmp` and `rpmvercmp` C functions directly into the script. This eliminates 100% of the subprocess overhead for version comparisons.

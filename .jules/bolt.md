## 2024-05-24 - Pure-Python Version Comparisons
**Learning:** Shelling out to `vercmp` for N+1 package version comparisons using `bash -c` is a massive performance bottleneck. However, `pkg_resources` or `packaging.version` cannot be used to compare Arch Linux package versions since PEP 440 fundamentally disagrees with ALPM (e.g. `1.0a` evaluates as older than `1.0` in ALPM).
**Action:** Always use a custom pure-Python port of Pacman's `alpm_vercmp` (and `rpmvercmp`) logic for Arch package comparisons in Python scripts.

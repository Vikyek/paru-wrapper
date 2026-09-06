## 2024-05-24 - Pure-Python Version Comparisons
**Learning:** Shelling out to `vercmp` for N+1 package version comparisons using `bash -c` is a massive performance bottleneck. However, `pkg_resources` or `packaging.version` cannot be used to compare Arch Linux package versions since PEP 440 fundamentally disagrees with ALPM (e.g. `1.0a` evaluates as older than `1.0` in ALPM).
**Action:** Always use a custom pure-Python port of Pacman's `alpm_vercmp` (and `rpmvercmp`) logic for Arch package comparisons in Python scripts.
## 2024-09-04 - [Cache bypass falsy evaluation on empty set]
**Learning:** Checking a cache implementation in Python using `if _installed_cache:` fails when the cache is an intentionally empty collection (like `set()`), as it evaluates to `False`. This causes the script to inadvertently bypass the O(1) bulk cache and silently fallback to O(N) operations.
**Action:** Always check cache initialization with strict equality (e.g., `if _installed_cache is not None:`) rather than rely on truthiness, especially when an empty collection is a valid cached state.

## 2024-09-04 - [Pacman query optimization pitfall]
**Learning:** Optimizing AUR package filtering in bash by matching against locally installed foreign packages (`pacman -Qmq`) is faster than filtering out official repo packages (`pacman -Slq`), but it introduces a critical regression: it completely ignores newly requested packages that are not yet installed on the system.
**Action:** Performance optimizations that reduce lookup space must not exclude required domains (like pending installations). Always verify that the "faster" query command actually covers all edge cases (new vs installed) before optimizing.

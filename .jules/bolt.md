## 2023-10-24 - Subprocess N+1 Bottlenecks
**Learning:** Shell wrapper scripts often cause O(N) subprocess overhead by calling commands like `pacman -Si` individually per package instead of batch querying with `pacman -Sl`.
**Action:** Look for loops running shell commands (especially package managers) and replace them with single batched commands where output can be parsed.
## 2023-10-24 - Bash string matching
**Learning:** Forking subprocesses like `echo` and `grep` inside a loop over a potentially large list causes significant overhead.
**Action:** Use pure bash substring matching (e.g. `[[ "$new_deps_padded" == *$'
'"$orphan"$'
'* ]]`) to process lists efficiently without leaving the shell.
## 2026-08-29 - Subprocess Overhead Optimization in update_mkvpkg_aur.py
**Learning:** For-loops running subprocess calls (like `vercmp` and `repo-remove`) for every package create massive overhead (N+1 query problem) in Python scripts.
**Action:** Always look for opportunities to early return/skip unnecessary subprocess calls (e.g. `aur_ver == local_ver`), and batch commands that accept multiple arguments (like `repo-remove`) into a single subprocess call.

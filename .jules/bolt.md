## 2023-10-24 - Subprocess N+1 Bottlenecks
**Learning:** Shell wrapper scripts often cause O(N) subprocess overhead by calling commands like `pacman -Si` individually per package instead of batch querying with `pacman -Sl`.
**Action:** Look for loops running shell commands (especially package managers) and replace them with single batched commands where output can be parsed.
## 2023-10-24 - Bash string matching
**Learning:** Forking subprocesses like `echo` and `grep` inside a loop over a potentially large list causes significant overhead.
**Action:** Use pure bash substring matching (e.g. `[[ "$new_deps_padded" == *$'
'"$orphan"$'
'* ]]`) to process lists efficiently without leaving the shell.
## 2024-05-14 - Optimize update_mkvpkg_aur.py subprocess spawns
**Learning:** Subprocess creation in Python scripts is a significant bottleneck when called repetitively in a loop (e.g., `vercmp` on matching string versions or `repo-remove` for individual packages).
**Action:** When working with Python wrapper scripts for system tools, always check for early return opportunities to avoid spawning subprocesses, and batch arguments into single subprocess calls whenever possible.

## 2023-10-24 - Subprocess N+1 Bottlenecks
**Learning:** Shell wrapper scripts often cause O(N) subprocess overhead by calling commands like `pacman -Si` individually per package instead of batch querying with `pacman -Sl`.
**Action:** Look for loops running shell commands (especially package managers) and replace them with single batched commands where output can be parsed.
## 2023-10-24 - Bash string matching
**Learning:** Forking subprocesses like `echo` and `grep` inside a loop over a potentially large list causes significant overhead.
**Action:** Use pure bash substring matching (e.g. `[[ "$new_deps_padded" == *$'
'"$orphan"$'
'* ]]`) to process lists efficiently without leaving the shell.
## 2023-10-24 - Dependency parsing bug with tr
**Learning:** Using `tr -d '>=<0-9.'` to strip version operators out of package names is extremely dangerous because it corrupts any package that genuinely has numbers in its name (e.g. gcc11 -> gcc, lib32-glibc -> lib-glibc).
**Action:** Use `sed 's/[<>=].*//'` or similar regex that stops exactly at the version operators to safely truncate package dependency strings.

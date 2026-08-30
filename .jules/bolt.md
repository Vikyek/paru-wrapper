## 2023-10-24 - Subprocess N+1 Bottlenecks
**Learning:** Shell wrapper scripts often cause O(N) subprocess overhead by calling commands like `pacman -Si` individually per package instead of batch querying with `pacman -Sl`.
**Action:** Look for loops running shell commands (especially package managers) and replace them with single batched commands where output can be parsed.
## 2023-10-24 - Bash string matching
**Learning:** Forking subprocesses like `echo` and `grep` inside a loop over a potentially large list causes significant overhead.
**Action:** Use pure bash substring matching (e.g. `[[ "$new_deps_padded" == *$'
'"$orphan"$'
'* ]]`) to process lists efficiently without leaving the shell.
## 2026-08-30 - Fix repo-remove security validation and merge conflict
**Learning:** When adding `--` to separate arguments from flags in bash commands executed via `subprocess.run`, ensure the `--` is placed *after* all the necessary command options (e.g. `["repo-remove", "-w", "--", db_path]...` would treat `db_path` as a package name, whereas `["repo-remove", "-w", db_path, "--"]...` correctly limits parsing only for the package names. However `pacman` tooling stops parsing options at the first non-option argument, so `db_path` itself is enough to stop option parsing. If `--` is still required by linters, place it correctly before the untrusted arguments and after any positional arguments that require escaping.
**Action:** Always test the position of `--` when using tools like `repo-remove` or `repo-add` in a subprocess, and ensure the script integrates correctly with `locals()` checks from upstream commits to avoid breaking the build during a merge.

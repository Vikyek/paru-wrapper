## 2024-05-24 - Consistent list output in bash arrays
**Learning:** Found an existing pattern in `paru-wrapper` where array elements are iterated and printed as `  -> $(basename "$pkg")`. This format is cleaner than printing `echo "Array: ${array[*]}"` which causes a jagged wall of text.
**Action:** When printing multiple packages (like orphans to remove), reuse this bulleted pattern (`  -> pkgname`) to ensure consistency and readability across the script.
## 2024-06-25 - Python Print to Stderr conversion

**Learning:** When converting standard `print()` statements to `sys.stderr.write()` for better stdout/stderr separation in CLI tools, the `\n` newline character must be manually appended to the string format, as `sys.stderr.write` does not automatically append newlines like `print()` does.

**Action:** Always append `\n` when rewriting Python `print` lines to use `sys.stderr.write`.
## 2026-09-01 - Conditionally formatting ANSI colors in Python scripts
**Learning:** Raw ANSI escape codes emitted to `stderr` or `stdout` can corrupt pipelines and logs for automated tools and CI systems if they are not disabled properly.
**Action:** When adding semantic colors to Python scripts, conditionally apply them by checking both `os.environ.get("NO_COLOR")` and `sys.stderr.isatty()` (or `sys.stdout.isatty()`) to ensure machine-readability is preserved.
## 2024-05-19 - Safe In-Place Progress Bars in Shell Wrappers
**Learning:** Using `echo -ne "\r\033[K..."` is an extremely effective way to create in-place updating progress counters in pure bash. However, it requires safe fallback behavior via `[ -t 2 ]` and `[ -z "${NO_COLOR:-}" ]` to prevent breaking piped scripts, CI environments, and stdout logging (by keeping output on stderr `>&2`).
**Action:** When implementing CLI progress indicators in raw shell environments, always check if standard error (or stdout if writing there) is connected to a TTY (`-t 2`) and respect `NO_COLOR` before injecting carriage returns and ANSI line-clearing escapes. Provide a clean, non-spammy fallback for non-TTY environments.

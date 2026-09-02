## 2024-05-24 - Consistent list output in bash arrays
**Learning:** Found an existing pattern in `paru-wrapper` where array elements are iterated and printed as `  -> $(basename "$pkg")`. This format is cleaner than printing `echo "Array: ${array[*]}"` which causes a jagged wall of text.
**Action:** When printing multiple packages (like orphans to remove), reuse this bulleted pattern (`  -> pkgname`) to ensure consistency and readability across the script.
## 2024-06-25 - Python Print to Stderr conversion

**Learning:** When converting standard `print()` statements to `sys.stderr.write()` for better stdout/stderr separation in CLI tools, the `\n` newline character must be manually appended to the string format, as `sys.stderr.write` does not automatically append newlines like `print()` does.

**Action:** Always append `\n` when rewriting Python `print` lines to use `sys.stderr.write`.
## 2026-09-01 - Conditionally formatting ANSI colors in Python scripts
**Learning:** Raw ANSI escape codes emitted to `stderr` or `stdout` can corrupt pipelines and logs for automated tools and CI systems if they are not disabled properly.
**Action:** When adding semantic colors to Python scripts, conditionally apply them by checking both `os.environ.get("NO_COLOR")` and `sys.stderr.isatty()` (or `sys.stdout.isatty()`) to ensure machine-readability is preserved.
## 2024-05-14 - Semantic colors in bash scripts with set -u
**Learning:** When adding ANSI color codes to bash scripts that run with `set -u` (unbound variables cause errors), safely check the `NO_COLOR` environment variable using a fallback like `[ -z "${NO_COLOR:-}" ]`. Additionally, use `[ -t 1 ]` or `[ -t 2 ]` to ensure the target output stream is a terminal before applying colors, avoiding leaking ANSI escapes into logs or pipelines.
**Action:** Use `if [ -z "${NO_COLOR:-}" ] && [ -t 2 ]; then` to conditionally define color variables at the script's initialization phase.

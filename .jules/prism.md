## 2024-05-24 - Consistent list output in bash arrays
**Learning:** Found an existing pattern in `paru-wrapper` where array elements are iterated and printed as `  -> $(basename "$pkg")`. This format is cleaner than printing `echo "Array: ${array[*]}"` which causes a jagged wall of text.
**Action:** When printing multiple packages (like orphans to remove), reuse this bulleted pattern (`  -> pkgname`) to ensure consistency and readability across the script.
## 2024-06-25 - Python Print to Stderr conversion

**Learning:** When converting standard `print()` statements to `sys.stderr.write()` for better stdout/stderr separation in CLI tools, the `\n` newline character must be manually appended to the string format, as `sys.stderr.write` does not automatically append newlines like `print()` does.

**Action:** Always append `\n` when rewriting Python `print` lines to use `sys.stderr.write`.

## 2024-05-24 - Consistent list output in bash arrays
**Learning:** Found an existing pattern in `paru-wrapper` where array elements are iterated and printed as `  -> $(basename "$pkg")`. This format is cleaner than printing `echo "Array: ${array[*]}"` which causes a jagged wall of text.
**Action:** When printing multiple packages (like orphans to remove), reuse this bulleted pattern (`  -> pkgname`) to ensure consistency and readability across the script.

## 2026-09-07 - Bash Colorizing Edge Cases
**Learning:** When writing replacement regexes or strings to add ANSI colors in bash, if there is logic using identical localized variable names (`c_info='\e[1;34m'`), it requires extra manual refactoring beyond simple regex replacements to avoid duplicating color escapes and preserve clean formatting for strings.
**Action:** Be sure to extract hardcoded color assignments into global, standardized color functions to prevent duplication and simplify string formatting moving forward.

## 2024-05-24 - Command Injection via eval echo
**Vulnerability:** Found a command injection vulnerability in `pacman-wrapper` where user input (`$SUDO_USER`) was passed directly into an `eval` statement: `USER_HOME=$(eval echo "~$SUDO_USER")`.
**Learning:** Using `eval` with unvalidated input (even seemingly benign environment variables like `SUDO_USER` which can be manipulated by attackers) is extremely dangerous and allows arbitrary code execution with the privileges of the running script.
**Prevention:** Avoid `eval` for expanding home directories. Instead, use secure, built-in methods or external tools designed for this purpose, such as `getent passwd "$SUDO_USER" | cut -d: -f6`.

## 2024-08-29 - Command Injection in Bash Arithmetic Evaluation
**Vulnerability:** Found a command injection vulnerability in `pacman-wrapper` where unvalidated data read from a cache file (`$CACHE_DIR/paru_completed_packages`) was evaluated in a bash arithmetic context: `completed=$((completed + 1))`. Malicious payload like `a[$(id > /tmp/pwned)]` in the file leads to arbitrary code execution when evaluated.
**Learning:** Bash arithmetic expansion (`$((...))`) evaluates string content as an expression. If the string contains command substitutions or arrays indexing with command substitutions, they will be executed, making it a powerful but often overlooked vector for command injection.
**Prevention:** Always sanitize variables before using them in bash arithmetic evaluation, especially when sourced from files, user input, or environment variables. Using `${var//[^0-9]/}` to strip non-numeric characters before evaluation prevents command injection.

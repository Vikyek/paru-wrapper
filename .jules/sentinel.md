## 2024-05-24 - Command Injection via eval echo
**Vulnerability:** Found a command injection vulnerability in `pacman-wrapper` where user input (`$SUDO_USER`) was passed directly into an `eval` statement: `USER_HOME=$(eval echo "~$SUDO_USER")`.
**Learning:** Using `eval` with unvalidated input (even seemingly benign environment variables like `SUDO_USER` which can be manipulated by attackers) is extremely dangerous and allows arbitrary code execution with the privileges of the running script.
**Prevention:** Avoid `eval` for expanding home directories. Instead, use secure, built-in methods or external tools designed for this purpose, such as `getent passwd "$SUDO_USER" | cut -d: -f6`.
## $(date +%Y-%m-%d) - Command Option Injection in pacman wrappers
**Vulnerability:** Command option injection where untrusted package names starting with `-` could be interpreted as options by pacman.
**Learning:** Untrusted arrays passed to commands should always be prefixed with `--` to signify the end of options.
**Prevention:** Use `--` before expanding variables or arrays that contain user-provided or dynamic data when calling commands like `pacman`, `rm`, etc.

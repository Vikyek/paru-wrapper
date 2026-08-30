## 2024-05-24 - Command Injection via eval echo
**Vulnerability:** Found a command injection vulnerability in `pacman-wrapper` where user input (`$SUDO_USER`) was passed directly into an `eval` statement: `USER_HOME=$(eval echo "~$SUDO_USER")`.
**Learning:** Using `eval` with unvalidated input (even seemingly benign environment variables like `SUDO_USER` which can be manipulated by attackers) is extremely dangerous and allows arbitrary code execution with the privileges of the running script.
**Prevention:** Avoid `eval` for expanding home directories. Instead, use secure, built-in methods or external tools designed for this purpose, such as `getent passwd "$SUDO_USER" | cut -d: -f6`.

## 2024-08-30 - Bash Arithmetic Command Injection
**Vulnerability:** Command injection in `pacman-wrapper` through arithmetic evaluation (`$((completed + 1))`). The `completed` and `total` variables were read directly from cache files without sanitization. An attacker could craft a payload in these files that executes arbitrary commands.
**Learning:** Using `$((...))` with unvalidated variables allows attackers to inject commands or references that Bash evaluates directly. Always sanitize untrusted variables before using them in arithmetic evaluation, especially when data is read from potentially writable files.
**Prevention:** Sanitize the variables by stripping non-numeric characters (e.g., `var="${var//[^0-9]/}"`) and parse the sanitized values explicitly as decimal (e.g., with `10#$var`) before performing any arithmetic evaluation. Also provide a fallback value in case they become empty.

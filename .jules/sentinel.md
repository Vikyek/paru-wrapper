## 2024-05-24 - Command Injection via eval echo
**Vulnerability:** Found a command injection vulnerability in `pacman-wrapper` where user input (`$SUDO_USER`) was passed directly into an `eval` statement: `USER_HOME=$(eval echo "~$SUDO_USER")`.
**Learning:** Using `eval` with unvalidated input (even seemingly benign environment variables like `SUDO_USER` which can be manipulated by attackers) is extremely dangerous and allows arbitrary code execution with the privileges of the running script.
**Prevention:** Avoid `eval` for expanding home directories. Instead, use secure, built-in methods or external tools designed for this purpose, such as `getent passwd "$SUDO_USER" | cut -d: -f6`.

## 2025-01-09 - Fix URL Encoding Vulnerability in AUR RPC Call
**Vulnerability:** URL injection vulnerability via direct string interpolation of an unescaped package name (`$pkg`) into a `curl` GET request URL.
**Learning:** Bash string interpolation within URLs can lead to broken requests or parameter injection if the variables contain special characters (like `&`, `=`, or `+`). Using `curl`'s built-in parameter encoding features is safer and cleaner than manual interpolation.
**Prevention:** Always use `curl -G` with `--data-urlencode` to securely pass dynamic data as URL query parameters in Bash scripts.

## 2025-01-09 - Command Option Injection in pacman wrappers
**Vulnerability:** Command option injection where untrusted package names starting with `-` could be interpreted as options by pacman.
**Learning:** Untrusted arrays passed to commands should always be prefixed with `--` to signify the end of options.
**Prevention:** Use `--` before expanding variables or arrays that contain user-provided or dynamic data when calling commands like `pacman`, `rm`, etc.

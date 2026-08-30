## 2024-05-24 - Command Injection via eval echo
**Vulnerability:** Found a command injection vulnerability in `pacman-wrapper` where user input (`$SUDO_USER`) was passed directly into an `eval` statement: `USER_HOME=$(eval echo "~$SUDO_USER")`.
**Learning:** Using `eval` with unvalidated input (even seemingly benign environment variables like `SUDO_USER` which can be manipulated by attackers) is extremely dangerous and allows arbitrary code execution with the privileges of the running script.
**Prevention:** Avoid `eval` for expanding home directories. Instead, use secure, built-in methods or external tools designed for this purpose, such as `getent passwd "$SUDO_USER" | cut -d: -f6`.
## 2024-05-24 - Bash Arithmetic Command Injection and Symlink Overwrite
**Vulnerability:** Command injection / Local Privilege Escalation (LPE) via bash arithmetic evaluation in `pacman-wrapper`, and arbitrary file overwrite via symlink attack when writing to user-controlled cache directories as root.
**Learning:** Bash arithmetic evaluation (e.g. `completed=$((completed + 1))`) and integer comparisons (e.g. `[ "$total" -gt 0 ]`) evaluate strings as expressions. If a user-controlled variable contains a payload like `'a[$(id > /tmp/pwn)]'`, it is executed during arithmetic evaluation. Additionally, `pacman-wrapper` running as root wrote to a user-owned directory (`$CACHE_DIR`), allowing the user to create a symlink and overwrite arbitrary system files.
**Prevention:** Sanitize integer variables by stripping non-numeric characters (e.g., `var="${var//[^0-9]/}"`) before any arithmetic operation. Use `rm -f` before writing to files in user-controlled directories to destroy potential symlinks, or write securely without following symlinks.
## 2024-08-31 - [Prevent URL Injection in curl calls]
**Vulnerability:** URL injection vulnerability via string interpolation of `$pkg` inside a `curl` call in bash script.
**Learning:** Hardcoding unsanitized input directly into a URL string opens the script to unintended argument injection/query parameter manipulation. Even though the vulnerability is simple, using standard string interpolation without escaping the input can introduce unintended logical bugs or severe injection flaws if an attacker manages to control the package name string. In addition, always be careful to limit your patch to exactly the fix so that the review system does not flag pre-existing syntax errors.
**Prevention:** Instead of string interpolation, use `curl -G` (to send a GET request) alongside `--data-urlencode "key=value"` to securely pass and automatically URL-encode dynamic query parameters.
## 2026-08-30 - Fix Arbitrary Code Execution and TOCTOU Vulnerabilities in Pacman Wrappers
**Vulnerability:**
- Arbitrary Code Execution (ACE) via `eval` on the `SUDO_USER` environment variable.
- Command Injection via arithmetic expansion `$((completed + 1))` using potentially polluted file contents.
- Time-of-Check to Time-of-Use (TOCTOU) symlink vulnerabilities during sequential cache writing.
- Argument Option Injection allowing bypassing `--noconfirm` if package names started with hyphens in `sudo pacman -Rns`.
**Learning:** Shell scripts running with elevated privileges (like `sudo pacman` wrappers) are highly susceptible to environment variable injection and TOCTOU attacks when caching shared state. Arithmetic expansion implicitly evaluates variables, requiring strict sanitization.
**Prevention:**
- Replace `eval` with secure lookup mechanisms like `getent passwd`.
- Strip non-numeric characters before performing bash arithmetic `(( ... ))`.
- Use `mktemp` and atomic `mv -f` instead of directly echoing into user-controlled temporary files.
- Always prepend `--` when expanding arrays that may contain untrusted strings used as command arguments.

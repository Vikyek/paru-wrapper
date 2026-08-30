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

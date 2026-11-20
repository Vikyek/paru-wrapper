#!/usr/bin/env python3
"""
Updates the custom local package repository by querying the Arch User Repository (AUR)
and removing standard, unmodified AUR packages from the local DB when a newer version
is available remotely. This triggers a rebuild/upgrade during the next paru sync.
"""
import subprocess
import os
import urllib.request
import urllib.parse
import json
import sys
import time

db_path = os.environ.get("PARU_WRAPPER_REPO_DB", "")
projects_dir = os.environ.get("PARU_WRAPPER_PROJECTS_DIR", "")
repo_name = os.environ.get("PARU_WRAPPER_REPO", "")
auto_update_installed_env = os.environ.get("PARU_WRAPPER_AUTO_UPDATE_INSTALLED", "true").lower()
auto_update_installed = auto_update_installed_env in ("true", "1", "yes", "on")


def get_makepkg_gpgkey():
    """
    Resolves the GPG signing key from environment variables or makepkg.conf.

    @returns Key fingerprint/ID string if configured, otherwise an empty string
    """
    env_key = os.environ.get("PARU_WRAPPER_GPGKEY") or os.environ.get("GPGKEY")
    if env_key:
        return env_key.strip().strip("'\"")

    home = os.environ.get("HOME", "")
    conf_paths = [os.path.join(home, ".makepkg.conf")] if home else []
    conf_paths.append("/etc/makepkg.conf")
    for conf in conf_paths:
        if not os.path.isfile(conf):
            continue
        found = ""
        try:
            with open(conf, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        continue
                    if stripped.startswith("GPGKEY") and "=" in stripped:
                        key_part, val_part = stripped.split("=", 1)
                        if key_part.strip() == "GPGKEY":
                            val = val_part.split("#", 1)[0].strip().strip("'\"")
                            if val:
                                found = val
        except OSError:
            continue
        if found:
            return found
    return ""

def run_cmd(cmd):
    """
    Executes an executable with its arguments and returns its standard output.
    Silently catches execution and process errors, returning an empty string on failure.

    @param cmd - List of command arguments (e.g., ['pacman', '-Sl', 'repo'])
    @returns Stripped standard output string, or an empty string if it fails
    """
    try:
        return subprocess.check_output(cmd, text=True).strip() # nosec
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return ""

def parse_evr(evr: str):
    """
    Parses an Arch Linux EVR (Epoch, Version, Release) string into its components.

    @param evr - The full EVR version string (e.g., '1:2.3-4')
    @returns A tuple containing (epoch, version, release) as (str, str, str | None); release is None when the input has no '-' separator
    """
    s = 0
    while s < len(evr) and evr[s].isdigit(): s += 1
    se = evr.rfind('-')
    if s < len(evr) and evr[s] == ':':
        epoch = evr[:s] or "0"
        version_start = s + 1
    else:
        epoch, version_start = "0", 0
    if se != -1 and se >= version_start:
        return epoch, evr[version_start:se], evr[se+1:]
    return epoch, evr[version_start:], None

def rpmvercmp(a: str, b: str) -> int:
    """
    Compares two version or release string segments using the rpmvercmp algorithm.

    @param a - The first version segment
    @param b - The second version segment
    @returns 1 if a > b, -1 if a < b, 0 if they are equal
    """
    a, b = str(a), str(b)
    if a == b: return 0
    p1, p2, l1, l2 = 0, 0, len(a), len(b)
    while p1 < l1 and p2 < l2:
        o1, o2 = p1, p2
        while o1 < l1 and not a[o1].isalnum(): o1 += 1
        while o2 < l2 and not b[o2].isalnum(): o2 += 1
        if o1 == l1 and o2 == l2:
            p1, p2 = o1, o2
            break
        if (o1 - p1) != (o2 - p2): return -1 if (o1 - p1) < (o2 - p2) else 1
        p1, p2 = o1, o2
        isnum = a[p1].isdigit() if p1 < l1 else False
        while p1 < l1 and (a[p1].isdigit() if isnum else a[p1].isalpha()): p1 += 1
        while p2 < l2 and (b[p2].isdigit() if isnum else b[p2].isalpha()): p2 += 1
        if o1 == p1: return -1
        if o2 == p2: return 1 if isnum else -1
        s1, s2 = a[o1:p1], b[o2:p2]
        if isnum:
            s1, s2 = s1.lstrip('0'), s2.lstrip('0')
            if len(s1) != len(s2): return 1 if len(s1) > len(s2) else -1
        if s1 != s2: return -1 if s1 < s2 else 1
    if p1 == l1 and p2 == l2: return 0
    if (p1 == l1 and (p2 < l2 and not b[p2].isalpha())) or (p1 < l1 and a[p1].isalpha()): return -1
    return 1

def alpm_vercmp(a: str, b: str) -> int:
    """
    Compares two ALPM version strings using epoch, version, and release.

    @param a - The first version string
    @param b - The second version string
    @returns 1 if a > b, -1 if a < b, 0 if equal
    """
    if a == b: return 0
    if not a or not b: return -1 if not a else 1
    e1, v1, r1 = parse_evr(a)
    e2, v2, r2 = parse_evr(b)
    ret = rpmvercmp(e1, e2)
    if ret == 0:
        ret = rpmvercmp(v1, v2)
        if ret == 0 and r1 is not None and r2 is not None:
            ret = rpmvercmp(r1, r2)
    return ret

_installed_cache = None

def clear_installed_cache():
    """Clears the cached set of installed packages."""
    global _installed_cache
    _installed_cache = None

def is_installed(pkg):
    """
    Checks if a given package is currently installed on the system.

    @param pkg - The name of the package to check
    @returns True if installed, False otherwise
    """
    global _installed_cache
    if _installed_cache is None:
        try:
            res = subprocess.run(["pacman", "-Qq"], capture_output=True, text=True, check=True) # nosec
            _installed_cache = set(res.stdout.splitlines())
        except Exception:
            _installed_cache = None

    if _installed_cache is not None:
        return pkg in _installed_cache

    try:
        res = subprocess.run(["pacman", "-Qq", pkg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) # nosec
        return res.returncode == 0
    except Exception:
        return False

def get_mkvpkg_packages_and_versions():
    """
    Returns a dictionary of {pkg_name: version} for all packages in the repo.
    Uses 'pacman -Sl <repo>' to get all packages and versions in a single subprocess call,
    avoiding the N+1 query problem of calling 'pacman -Si' for every package.

    @returns Dictionary of package names to version strings
    """
    if not repo_name:
        return {}
    output = run_cmd(["pacman", "-Sl", repo_name])
    packages = {}
    if output:
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[0] == repo_name:
                # parts[0] is repo, parts[1] is name, parts[2] is version
                packages[parts[1]] = parts[2]
    return packages

import http.client

def query_aur(packages):
    """
    Resolves the AUR package metadata in batched chunks to prevent URL length limits.

    @param packages - List of package names to query
    @returns Dictionary of package names to version strings
    @throws {RuntimeError} When the remote RPC endpoint cannot be reached or parsing fails
    """
    results = {}
    for i in range(0, len(packages), 50):
        batch = packages[i:i+50]
        query_args = [('v', '5'), ('type', 'info')]
        for pkg in batch:
            query_args.append(('arg[]', pkg))
        params = urllib.parse.urlencode(query_args)
        url = f"https://aur.archlinux.org/rpc/?{params}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'paru-wrapper-updater'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                if isinstance(data, dict):
                    for res in data.get('results', []):
                        if isinstance(res, dict) and 'Name' in res and 'Version' in res:
                            results[res['Name']] = res['Version']
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, http.client.HTTPException, UnicodeDecodeError) as e:
            raise RuntimeError(f"Error querying AUR for batch: {e}") from e
    return results

def is_live_repo_tool_pid(pid_str: str) -> bool:
    """Checks whether a lockfile PID corresponds to an active repo-add/repo-remove process."""
    if not pid_str.isdigit():
        return False
    pid = int(pid_str)
    if pid <= 0:
        return False
    proc_dir = f"/proc/{pid}"
    if not os.path.isdir(proc_dir):
        return False
    try:
        with open(os.path.join(proc_dir, "stat"), "r", encoding="utf-8", errors="replace") as f:
            stat_line = f.read()
        rparen = stat_line.rfind(")")
        if rparen != -1:
            after = stat_line[rparen + 1:].lstrip().split()
            if after and after[0] == "Z":
                return False
    except OSError:
        pass
    try:
        with open(os.path.join(proc_dir, "cmdline"), "rb") as f:
            raw_cmd = f.read()
        if not raw_cmd:
            return False
        args = [arg.decode("utf-8", errors="replace") for arg in raw_cmd.split(b"\0") if arg]
        return any(os.path.basename(arg) in ("repo-add", "repo-remove", "repo-elephant") for arg in args)
    except OSError:
        return os.path.isdir(proc_dir)


def ensure_repo_lock_clear(db_path: str, timeout: int = 120) -> bool:
    """
    Removes stale repo DB lockfiles left behind by dead/crashed repo-add/repo-remove
    processes and waits up to `timeout` seconds if an active process holds the lock.

    @param db_path - Path to the repository database archive
    @param timeout - Maximum seconds to wait for an active lock holder
    @returns True if the lockfile is clear, False if still held after timeout or unremovable
    """
    lockfile = f"{db_path}.lck"
    if not os.path.lexists(lockfile):
        return True

    deadline = time.monotonic() + max(0, timeout)
    last_log = 0.0

    while True:
        if not os.path.lexists(lockfile):
            return True

        try:
            with open(lockfile, "r", encoding="utf-8", errors="replace") as f:
                raw_content = f.read()
            pid_str = raw_content.strip()
        except FileNotFoundError:
            return True
        except OSError as e:
            sys.stderr.write(f"⚠ [update_mkvpkg_aur] Warning: Could not read lockfile '{lockfile}': {e}\n")
            return False

        if not pid_str:
            # Give a newly created empty lockfile a brief grace window to flush its PID
            try:
                age = time.time() - os.lstat(lockfile).st_mtime
            except FileNotFoundError:
                return True
            except OSError:
                age = 5.0
            if age < 5.0 and time.monotonic() < deadline:
                time.sleep(min(1.0, max(0.05, deadline - time.monotonic())))
                continue
            try:
                with open(lockfile, "r", encoding="utf-8", errors="replace") as f:
                    if f.read().strip() == "":
                        os.unlink(lockfile)
                        sys.stderr.write(f"⚠ [update_mkvpkg_aur] Removed stale empty repository lockfile: {lockfile}\n")
                        return True
            except FileNotFoundError:
                return True
            except OSError as e:
                sys.stderr.write(f"⚠ [update_mkvpkg_aur] Warning: Failed to remove stale lockfile '{lockfile}': {e}\n")
                return False
            continue

        if not is_live_repo_tool_pid(pid_str):
            try:
                with open(lockfile, "r", encoding="utf-8", errors="replace") as f:
                    if f.read().strip() == raw_content.strip():
                        os.unlink(lockfile)
                        sys.stderr.write(
                            f"⚠ [update_mkvpkg_aur] Removed stale repository lockfile '{lockfile}' "
                            f"(PID {pid_str} is no longer active).\n"
                        )
                        return True
            except FileNotFoundError:
                return True
            except OSError as e:
                sys.stderr.write(f"⚠ [update_mkvpkg_aur] Warning: Failed to remove stale lockfile '{lockfile}': {e}\n")
                return False
            continue

        now = time.monotonic()
        if now >= deadline:
            sys.stderr.write(
                f"⚠ [update_mkvpkg_aur] Warning: Timed out waiting for repository lockfile '{lockfile}' "
                f"held by active PID {pid_str}.\n"
            )
            return False

        if last_log == 0.0 or (now - last_log) >= 15.0:
            sys.stderr.write(
                f"[update_mkvpkg_aur] Waiting for active repository lockfile '{lockfile}' (PID {pid_str})...\n"
            )
            last_log = now

        time.sleep(min(1.0, max(0.05, deadline - now)))


def main():
    """
    Main execution entry point. Scans local repo, queries AUR, and unregisters
    outdated packages to force rebuilds during the next sync.
    """
    use_color = not os.environ.get("NO_COLOR") and sys.stderr.isatty()
    c_info = "\033[1;34m" if use_color else ""
    c_warn = "\033[1;33m" if use_color else ""
    c_error = "\033[1;31m" if use_color else ""
    c_reset = "\033[0m" if use_color else ""
    c_bold = "\033[1m" if use_color else ""

    db_changed = False
    if not db_path or not projects_dir or not repo_name:
        return
    if not os.path.exists(db_path):
        return

    # Use single pacman call to get all packages and versions
    pkg_versions = get_mkvpkg_packages_and_versions()
    unmodified_pkgs = []
    local_versions = {}

    for pkg, ver in pkg_versions.items():
        proj_path = os.path.join(projects_dir, pkg)
        if not os.path.isdir(proj_path):
            if ver:
                unmodified_pkgs.append(pkg)
                local_versions[pkg] = ver

    if not unmodified_pkgs:
        return

    aur_versions = query_aur(unmodified_pkgs)
    pkgs_to_remove = []

    vcs_replacements = []
    auto_upgrading = []
    skipping = []
    public_upgrades = []

    # Priority Check: If a non-git package exists in repo but a -git variant is installed,
    # auto-remove the non-git package to prevent conflicts and prioritize VCS versions.
    for pkg in unmodified_pkgs:
        if not pkg.endswith("-git"):
            if is_installed(f"{pkg}-git"):
                vcs_replacements.append(pkg)
                pkgs_to_remove.append(pkg)

    # Optimization: Use pure-Python alpm_vercmp to avoid subprocess overhead entirely
    for pkg in unmodified_pkgs:
        if pkg in vcs_replacements:
            continue
        aur_ver = aur_versions.get(pkg)
        local_ver = local_versions.get(pkg)
        if aur_ver and local_ver:
            if aur_ver == local_ver:
                continue
            try:
                res = alpm_vercmp(aur_ver, local_ver)
            except Exception as e:
                sys.stderr.write(f"{c_error}✖ Error{c_reset} in version comparison for {pkg}: {e}\n")
                res = 0

            if res > 0:
                if is_installed(pkg):
                    if auto_update_installed:
                        auto_upgrading.append((pkg, local_ver, aur_ver))
                        pkgs_to_remove.append(pkg)
                    else:
                        skipping.append((pkg, local_ver, aur_ver))
                else:
                    public_upgrades.append((pkg, local_ver, aur_ver))
                    pkgs_to_remove.append(pkg)

    if vcs_replacements:
        sys.stderr.write(f"\n{c_info}[paru-wrapper]{c_reset} Installed VCS packages take priority over non-git variants in {c_bold}{repo_name}{c_reset}. Removing non-git packages:\n")
        for pkg in vcs_replacements:
            sys.stderr.write(f"  -> {c_bold}{pkg}{c_reset} -> {c_bold}{pkg}-git{c_reset}\n")

    if auto_upgrading:
        sys.stderr.write(f"\n{c_info}[paru-wrapper]{c_reset} Newer versions found in AUR for installed packages. Auto-upgrading:\n")
        for pkg, local_ver, aur_ver in auto_upgrading:
            sys.stderr.write(f"  -> {c_bold}{pkg}{c_reset} ({local_ver} -> {c_bold}{aur_ver}{c_reset})\n")

    if skipping:
        sys.stderr.write(f"\n{c_info}[paru-wrapper]{c_reset} Newer versions found in AUR, but PARU_WRAPPER_AUTO_UPDATE_INSTALLED is disabled. Skipping auto-upgrade:\n")
        for pkg, local_ver, aur_ver in skipping:
            sys.stderr.write(f"  -> {c_bold}{pkg}{c_reset} ({local_ver} -> {c_bold}{aur_ver}{c_reset})\n")

    if public_upgrades:
        sys.stderr.write(f"\n{c_info}[paru-wrapper]{c_reset} Newer versions found in AUR for public packages. Removing from {c_bold}{repo_name}{c_reset} to trigger upgrade:\n")
        for pkg, local_ver, aur_ver in public_upgrades:
            sys.stderr.write(f"  -> {c_bold}{pkg}{c_reset} ({local_ver} -> {c_bold}{aur_ver}{c_reset})\n")

    # Optimization: Batch repo-remove operations to reduce subprocess overhead
    if pkgs_to_remove:
        # Re-read and revalidate package versions in repo to prevent removing newly indexed builds
        current_repo_versions = get_mkvpkg_packages_and_versions()
        validated_pkgs_to_remove = []
        for pkg in pkgs_to_remove:
            if pkg in vcs_replacements:
                validated_pkgs_to_remove.append(pkg)
                continue
            cur_ver = current_repo_versions.get(pkg)
            aur_v = aur_versions.get(pkg)
            if cur_ver and aur_v:
                try:
                    if alpm_vercmp(aur_v, cur_ver) > 0:
                        validated_pkgs_to_remove.append(pkg)
                except Exception:
                    pass

        pkgs_to_remove = validated_pkgs_to_remove

    if pkgs_to_remove:
        gpg_key = get_makepkg_gpgkey()
        try:
            for i in range(0, len(pkgs_to_remove), 100):
                if not ensure_repo_lock_clear(db_path):
                    sys.stderr.write(
                        f"{c_warn}⚠ [update_mkvpkg_aur] Warning:{c_reset} Skipping repo-remove because '{db_path}.lck' "
                        f"could not be acquired.\n"
                    )
                    break
                batch = pkgs_to_remove[i:i + 100]
                cmd = ["repo-remove", "-s"]
                if gpg_key:
                    cmd.extend(["-k", gpg_key])
                cmd.extend(["-w", "--", db_path] + batch)
                subprocess.run(cmd, check=True) # nosec
                db_changed = True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            sys.stderr.write(f"{c_warn}⚠ [update_mkvpkg_aur] Warning:{c_reset} Failed to run repo-remove: {e}\n")

    if db_changed:
        try:
            subprocess.run(["sudo", "pacman", "-Sy"], check=True) # nosec
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            sys.stderr.write(f"{c_warn}⚠ [update_mkvpkg_aur] Warning:{c_reset} Failed to sync database (pacman -Sy): {e}\n")

if __name__ == "__main__":
    main()

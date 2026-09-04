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

db_path = os.environ.get("PARU_WRAPPER_REPO_DB", "")
projects_dir = os.environ.get("PARU_WRAPPER_PROJECTS_DIR", "")
repo_name = os.environ.get("PARU_WRAPPER_REPO", "")
auto_update_installed_env = os.environ.get("PARU_WRAPPER_AUTO_UPDATE_INSTALLED", "true").lower()
auto_update_installed = auto_update_installed_env in ("true", "1", "yes", "on")

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
            _installed_cache = set()

    if _installed_cache:
        return pkg in _installed_cache

    try:
        res = subprocess.run(["pacman", "-Qq", pkg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) # nosec
        return res.returncode == 0
    except FileNotFoundError:
        return False

def get_mkvpkg_packages_and_versions():
    """
    Returns a dictionary of {pkg_name: version} for all packages in the repo.
    Uses 'pacman -Sl <repo>' to get all packages and versions in a single subprocess call,
    avoiding the N+1 query problem of calling 'pacman -Si' for every package.
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

def query_aur(packages):
    """
    Resolves the AUR package metadata in batched chunks to prevent URL length limits.

    @param packages - List of package names to query
    @returns Dictionary of package names to version strings
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
                for res in data.get('results', []):
                    results[res['Name']] = res['Version']
        except (urllib.error.URLError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Error querying AUR for batch: {e}") from e
    return results

def main():
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

    # Priority Check: If a non-git package exists in repo but a -git variant is installed,
    # auto-remove the non-git package to prevent conflicts and prioritize VCS versions.
    for pkg in unmodified_pkgs:
        if not pkg.endswith("-git"):
            if is_installed(f"{pkg}-git"):
                sys.stderr.write(f"{c_info}[paru-wrapper]{c_reset} Installed VCS package '{c_bold}{pkg}-git{c_reset}' takes priority over non-git '{c_bold}{pkg}{c_reset}' in {repo_name}. Removing non-git package...\n")
                pkgs_to_remove.append(pkg)

    # Optimization: Use pure-Python alpm_vercmp to avoid subprocess overhead entirely
    for pkg in unmodified_pkgs:
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
                        sys.stderr.write(f"{c_info}[paru-wrapper]{c_reset} Newer version {c_bold}{aur_ver}{c_reset} of installed package '{c_bold}{pkg}{c_reset}' found in AUR (local repo has {c_bold}{local_ver}{c_reset}). Auto-upgrading installation...\n")
                        pkgs_to_remove.append(pkg)
                    else:
                        sys.stderr.write(f"{c_info}[paru-wrapper]{c_reset} Newer version {c_bold}{aur_ver}{c_reset} of installed package '{c_bold}{pkg}{c_reset}' found in AUR, but PARU_WRAPPER_AUTO_UPDATE_INSTALLED is disabled. Skipping auto-upgrade.\n")
                else:
                    sys.stderr.write(f"{c_info}[paru-wrapper]{c_reset} Newer version {c_bold}{aur_ver}{c_reset} of public package '{c_bold}{pkg}{c_reset}' found in AUR (local repo has {c_bold}{local_ver}{c_reset}). Removing from {c_bold}{repo_name}{c_reset} to trigger upgrade...\n")
                    pkgs_to_remove.append(pkg)

    # Optimization: Batch repo-remove operations to reduce subprocess overhead
    if pkgs_to_remove:
        try:
            for i in range(0, len(pkgs_to_remove), 100):
                batch = pkgs_to_remove[i:i + 100]
                subprocess.run(["repo-remove", "-w", "--", db_path] + batch, check=True) # nosec
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

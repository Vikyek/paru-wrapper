#!/usr/bin/env python3
import subprocess
import os
import urllib.request
import json

db_path = os.environ.get("PARU_WRAPPER_REPO_DB", "")
projects_dir = os.environ.get("PARU_WRAPPER_PROJECTS_DIR", "")
repo_name = os.environ.get("PARU_WRAPPER_REPO", "")

def run_cmd(cmd):
    try:
        return subprocess.check_output(cmd, text=True).strip()
    except subprocess.CalledProcessError:
        return ""
    except Exception:
        return ""

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
            if len(parts) >= 3:
                # parts[0] is repo, parts[1] is name, parts[2] is version
                packages[parts[1]] = parts[2]
    return packages

def query_aur(packages):
    results = {}
    for i in range(0, len(packages), 50):
        batch = packages[i:i+50]
        params = "&".join(f"arg[]={pkg}" for pkg in batch)
        url = f"https://aur.archlinux.org/rpc/?v=5&type=info&{params}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'paru-wrapper-updater'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                for res in data.get('results', []):
                    results[res['Name']] = res['Version']
        except Exception as e:
            print(f"Error querying AUR for batch: {e}")
    return results

def main():
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
    db_changed = False

    to_compare = []
    for pkg in unmodified_pkgs:
        aur_ver = aur_versions.get(pkg)
        local_ver = local_versions.get(pkg)
        if aur_ver and local_ver:
            if aur_ver == local_ver:
                continue
            to_compare.extend([pkg, aur_ver, local_ver])

    if to_compare:
        script = """
        while [ $# -ge 3 ]; do
            pkg="$1"
            aur="$2"
            loc="$3"
            res=$(vercmp "$aur" "$loc" 2>/dev/null || echo 0)
            if [ "$res" -gt 0 ]; then
                echo "$pkg"
            fi
            shift 3
        done
        """
        newer_pkgs = []
        # Batch max 150 args (50 packages) at a time
        for i in range(0, len(to_compare), 150):
            batch = to_compare[i:i+150]
            try:
                out = subprocess.check_output(["bash", "-c", script, "--", *batch], text=True)  # nosec B603
                if out.strip():
                    newer_pkgs.extend(out.strip().splitlines())
            except Exception as e:
                print(f"Error in batch version comparison: {e}")

        if newer_pkgs:
            for pkg in newer_pkgs:
                print(f"[paru-wrapper] Newer version {aur_versions[pkg]} of public package '{pkg}' found in AUR (local repo has {local_versions[pkg]}). Removing from {repo_name} to trigger upgrade...")

            try:
                # Batch remove
                subprocess.run(["repo-remove", "-w", db_path, "--", *newer_pkgs], check=True)  # nosec B603
                db_changed = True
            except Exception as e:
                print(f"Error batch removing packages: {e}")

    if db_changed:
        subprocess.run(["sudo", "pacman", "-Sy"], check=True)

if __name__ == "__main__":
    main()

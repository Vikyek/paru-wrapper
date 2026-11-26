import os
import stat
import subprocess
import tempfile
import unittest

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
PARU_WRAPPER_PATH = os.path.join(REPO_DIR, "paru-wrapper")


class TestParuWrapperNetworkResume(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.home_dir = os.path.join(self.tmpdir.name, "home")
        self.cache_dir = os.path.join(self.tmpdir.name, "pacman-cache")
        self.clone_dir = os.path.join(self.tmpdir.name, "paru-clone")
        self.bin_dir = os.path.join(self.tmpdir.name, "bin")
        os.makedirs(self.home_dir)
        os.makedirs(self.cache_dir)
        os.makedirs(self.clone_dir)
        os.makedirs(self.bin_dir)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _base_env(self):
        env = os.environ.copy()
        env["HOME"] = self.home_dir
        env["XDG_CACHE_HOME"] = os.path.join(self.home_dir, ".cache")
        env["NO_COLOR"] = "1"
        env["PARU_CLONE_DIR"] = self.clone_dir
        env["PARU_WRAPPER_PART_SEARCH_DIRS"] = self.cache_dir
        env["PARU_WRAPPER_NET_POLL_INTERVAL"] = "1"
        env["PARU_WRAPPER_RETRY_DELAY"] = "0"
        return env

    def _write_exec(self, name, body):
        path = os.path.join(self.bin_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        return path

    def _run_sourced_bash(self, script, env=None):
        full_env = self._base_env()
        if env:
            full_env.update(env)
        cmd = [
            "bash",
            "-c",
            f'source "{PARU_WRAPPER_PATH}"\n{script}',
        ]
        return subprocess.run(cmd, env=full_env, capture_output=True, text=True)

    def test_offline_wait_and_resume_succeeds(self):
        """Mid-download network outage waits for connectivity and resumes paru."""
        state_file = os.path.join(self.tmpdir.name, "net_checks")
        paru_calls = os.path.join(self.tmpdir.name, "paru_calls")

        mock_paru = self._write_exec(
            "mock-paru",
            f"""#!/usr/bin/env bash
count=0
[[ -f "{paru_calls}" ]] && count=$(cat "{paru_calls}")
count=$((count + 1))
echo "$count" > "{paru_calls}"
if [[ $count -eq 1 ]]; then
    echo "error: failed retrieving file 'pkg-1-1-x86_64.pkg.tar.zst'" >&2
    exit 1
fi
echo "resumed and installed"
exit 0
""",
        )

        # Network probe fails on first 2 checks (initial drop + first poll), then recovers
        net_cmd = (
            f'c=0; [[ -f "{state_file}" ]] && c=$(cat "{state_file}"); '
            f'c=$((c + 1)); echo "$c" > "{state_file}"; '
            f'[[ $c -ge 3 ]]'
        )

        res = self._run_sourced_bash(
            "run_paru_with_clone_repair -Syu",
            env={
                "PARU_BIN": mock_paru,
                "PARU_WRAPPER_NET_CHECK_CMD": net_cmd,
                "PARU_WRAPPER_NET_WAIT_TIMEOUT": "10",
                "PARU_WRAPPER_NET_RETRY_MAX": "3",
            },
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        with open(paru_calls, encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "2")
        self.assertIn("Network connectivity lost", res.stderr)
        self.assertIn("Network connectivity restored. Resuming operation", res.stderr)

    def test_recent_part_file_resumes_when_network_flapped(self):
        """Transient drop leaving a .part file resumes even if network already recovered."""
        paru_calls = os.path.join(self.tmpdir.name, "paru_calls")
        part_file = os.path.join(self.cache_dir, "bigpkg-1.0-1-x86_64.pkg.tar.zst.part")

        mock_paru = self._write_exec(
            "mock-paru",
            f"""#!/usr/bin/env bash
count=0
[[ -f "{paru_calls}" ]] && count=$(cat "{paru_calls}")
count=$((count + 1))
echo "$count" > "{paru_calls}"
if [[ $count -eq 1 ]]; then
    sleep 0.05
    printf 'partial-bytes' > "{part_file}"
    exit 1
fi
rm -f "{part_file}"
exit 0
""",
        )

        res = self._run_sourced_bash(
            "run_paru_with_clone_repair -S bigpkg",
            env={
                "PARU_BIN": mock_paru,
                "PARU_WRAPPER_NET_CHECK_CMD": "true",
                "PARU_WRAPPER_PART_RETRY_MAX": "2",
                "PARU_WRAPPER_NET_RETRY_MAX": "5",
            },
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        with open(paru_calls, encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "2")
        self.assertIn("Detected interrupted partial download (.part)", res.stderr)

    def test_download_staging_dir_without_part_file_does_not_retry(self):
        """libalpm download-* staging dirs without .part files must not trigger retry."""
        paru_calls = os.path.join(self.tmpdir.name, "paru_calls")
        staging_dir = os.path.join(self.cache_dir, "download-a1b2c3")

        mock_paru = self._write_exec(
            "mock-paru",
            f"""#!/usr/bin/env bash
count=0
[[ -f "{paru_calls}" ]] && count=$(cat "{paru_calls}")
count=$((count + 1))
echo "$count" > "{paru_calls}"
sleep 0.05
mkdir -p "{staging_dir}"
exit 1
""",
        )

        res = self._run_sourced_bash(
            "run_paru_with_clone_repair -S bigpkg",
            env={
                "PARU_BIN": mock_paru,
                "PARU_WRAPPER_NET_CHECK_CMD": "true",
                "PARU_WRAPPER_PART_RETRY_MAX": "2",
                "PARU_WRAPPER_NET_RETRY_MAX": "5",
            },
        )
        self.assertEqual(res.returncode, 1)
        with open(paru_calls, encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "1")
        self.assertNotIn("Detected interrupted partial download (.part)", res.stderr)

    def test_non_network_error_does_not_retry(self):
        """Online non-network errors (e.g. target not found) exit immediately without retry."""
        paru_calls = os.path.join(self.tmpdir.name, "paru_calls")
        mock_paru = self._write_exec(
            "mock-paru",
            f"""#!/usr/bin/env bash
count=0
[[ -f "{paru_calls}" ]] && count=$(cat "{paru_calls}")
echo $((count + 1)) > "{paru_calls}"
exit 1
""",
        )

        res = self._run_sourced_bash(
            "run_paru_with_clone_repair -S missing-pkg",
            env={
                "PARU_BIN": mock_paru,
                "PARU_WRAPPER_NET_CHECK_CMD": "true",
                "PARU_WRAPPER_NET_RETRY_MAX": "5",
            },
        )
        self.assertEqual(res.returncode, 1)
        with open(paru_calls, encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "1")

    def test_signal_exit_does_not_retry_even_when_offline(self):
        """Signal exit codes (>128, e.g. SIGINT=130) must never be retried."""
        paru_calls = os.path.join(self.tmpdir.name, "paru_calls")
        mock_paru = self._write_exec(
            "mock-paru",
            f"""#!/usr/bin/env bash
count=0
[[ -f "{paru_calls}" ]] && count=$(cat "{paru_calls}")
echo $((count + 1)) > "{paru_calls}"
exit 130
""",
        )

        res = self._run_sourced_bash(
            "run_paru_with_clone_repair -Syu",
            env={
                "PARU_BIN": mock_paru,
                "PARU_WRAPPER_NET_CHECK_CMD": "false",
                "PARU_WRAPPER_NET_WAIT_TIMEOUT": "10",
            },
        )
        self.assertEqual(res.returncode, 130)
        with open(paru_calls, encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "1")

    def test_wait_disabled_with_zero_timeout_returns_failure(self):
        """PARU_WRAPPER_NET_WAIT_TIMEOUT=0 skips waiting and returns original failure."""
        paru_calls = os.path.join(self.tmpdir.name, "paru_calls")
        mock_paru = self._write_exec(
            "mock-paru",
            f"""#!/usr/bin/env bash
count=0
[[ -f "{paru_calls}" ]] && count=$(cat "{paru_calls}")
echo $((count + 1)) > "{paru_calls}"
exit 1
""",
        )

        res = self._run_sourced_bash(
            "run_paru_with_clone_repair -Syu",
            env={
                "PARU_BIN": mock_paru,
                "PARU_WRAPPER_NET_CHECK_CMD": "false",
                "PARU_WRAPPER_NET_WAIT_TIMEOUT": "0",
            },
        )
        self.assertEqual(res.returncode, 1)
        with open(paru_calls, encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "1")

    def test_broken_clone_waits_for_network_before_retry(self):
        """Corrupted clone cache repair waits if network is down before retrying."""
        broken_pkg_dir = os.path.join(self.clone_dir, "bad-aur-pkg")
        os.makedirs(broken_pkg_dir)
        state_file = os.path.join(self.tmpdir.name, "net_checks")
        paru_calls = os.path.join(self.tmpdir.name, "paru_calls")

        mock_paru = self._write_exec(
            "mock-paru",
            f"""#!/usr/bin/env bash
count=0
[[ -f "{paru_calls}" ]] && count=$(cat "{paru_calls}")
count=$((count + 1))
echo "$count" > "{paru_calls}"
if [[ $count -eq 1 ]]; then
    exit 1
fi
exit 0
""",
        )

        net_cmd = (
            f'c=0; [[ -f "{state_file}" ]] && c=$(cat "{state_file}"); '
            f'c=$((c + 1)); echo "$c" > "{state_file}"; '
            f'[[ $c -ge 2 ]]'
        )

        res = self._run_sourced_bash(
            "run_paru_with_clone_repair -S bad-aur-pkg",
            env={
                "PARU_BIN": mock_paru,
                "PARU_WRAPPER_NET_CHECK_CMD": net_cmd,
                "PARU_WRAPPER_NET_WAIT_TIMEOUT": "10",
            },
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        self.assertFalse(os.path.exists(broken_pkg_dir))
        with open(paru_calls, encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "2")
        self.assertIn("Auto-repairing corrupted clone cache: bad-aur-pkg", res.stderr)
        self.assertIn("Network connectivity lost during clone", res.stderr)

    def test_end_to_end_cli_execution_resumes_on_network_drop(self):
        """Executing paru-wrapper directly as a CLI command resumes interrupted downloads."""
        state_file = os.path.join(self.tmpdir.name, "net_checks")
        paru_calls = os.path.join(self.tmpdir.name, "paru_calls")
        mock_paru = self._write_exec(
            "mock-paru",
            f"""#!/usr/bin/env bash
count=0
[[ -f "{paru_calls}" ]] && count=$(cat "{paru_calls}")
count=$((count + 1))
echo "$count" > "{paru_calls}"
if [[ $count -eq 1 ]]; then
    exit 1
fi
exit 0
""",
        )

        net_cmd = (
            f'c=0; [[ -f "{state_file}" ]] && c=$(cat "{state_file}"); '
            f'c=$((c + 1)); echo "$c" > "{state_file}"; '
            f'[[ $c -ge 2 ]]'
        )

        env = self._base_env()
        env.update(
            {
                "PARU_BIN": mock_paru,
                "PARU_WRAPPER_NET_CHECK_CMD": net_cmd,
                "PARU_WRAPPER_NET_WAIT_TIMEOUT": "10",
            }
        )

        res = subprocess.run(
            [PARU_WRAPPER_PATH, "-Si", "example"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        with open(paru_calls, encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "2")


class TestParuWrapperSearchInstallDeferral(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.home_dir = os.path.join(self.tmpdir.name, "home")
        self.config_dir = os.path.join(self.tmpdir.name, "xdg_config")
        self.plugins_dir = os.path.join(self.config_dir, "paru-wrapper", "plugins.d")
        self.cache_dir = os.path.join(self.tmpdir.name, "cache")
        self.clone_dir = os.path.join(self.tmpdir.name, "paru-clone")
        self.bin_dir = os.path.join(self.tmpdir.name, "bin")
        for d in (
            self.home_dir,
            self.plugins_dir,
            self.cache_dir,
            self.clone_dir,
            self.bin_dir,
        ):
            os.makedirs(d)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write_exec(self, name, body):
        path = os.path.join(self.bin_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        return path

    def _setup_test_plugins(self, trace_file):
        # Override all default plugins in XDG_CONFIG_HOME so tests stay isolated
        plugin_body = f"""#!/bin/bash
plugin_hook() {{
    echo "hook:$1" >> "{trace_file}"
}}
"""
        for pname in (
            "10-snapper.sh",
            "20-anneal.sh",
            "30-rebuild-check.sh",
            "40-paru-completion.sh",
            "50-vault-sync.sh",
        ):
            with open(os.path.join(self.plugins_dir, pname), "w", encoding="utf-8") as f:
                f.write("#!/bin/bash\nplugin_hook() { :; }\n")

        with open(
            os.path.join(self.plugins_dir, "25-projects-pull.sh"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write(plugin_body)

    def _setup_mock_system_bins(self):
        self._write_exec(
            "pacman",
            """#!/usr/bin/env bash
if [[ "${1:-}" == "-Si" ]]; then
    for t in "${@:2}"; do
        if [[ "$t" == extra/* ]]; then
            echo "Repository      : extra"
            echo "Name            : ${t#*/}"
        fi
    done
    exit 0
fi
exit 0
""",
        )
        self._write_exec("sudo", "#!/usr/bin/env bash\nexit 0\n")

    def _base_env(self):
        env = os.environ.copy()
        env["HOME"] = self.home_dir
        env["XDG_CONFIG_HOME"] = self.config_dir
        env["XDG_CACHE_HOME"] = self.cache_dir
        env["NO_COLOR"] = "1"
        env["PARU_CLONE_DIR"] = self.clone_dir
        env["PATH"] = f"{self.bin_dir}:{env.get('PATH', '')}"
        return env

    def test_search_install_no_selection_skips_project_updates(self):
        """Running 'paru <name>' with no selection must never trigger projects-pull or post hooks."""
        trace_file = os.path.join(self.tmpdir.name, "trace.log")
        self._setup_test_plugins(trace_file)
        self._setup_mock_system_bins()

        mock_paru = self._write_exec(
            "mock-paru",
            f"""#!/usr/bin/env bash
echo "paru:select=${{PARU_SEARCH_SELECT_FILE:-}}:args=$*" >> "{trace_file}"
exit 0
""",
        )

        env = self._base_env()
        env["PARU_BIN"] = mock_paru

        res = subprocess.run(
            [PARU_WRAPPER_PATH, "ripgrep"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        with open(trace_file, encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        self.assertEqual(len(lines), 1, msg=lines)
        self.assertTrue(lines[0].startswith("paru:select="), msg=lines)
        self.assertTrue(lines[0].endswith(":args=ripgrep"), msg=lines)
        self.assertFalse(any(line.startswith("hook:") for line in lines), msg=lines)

    def test_search_install_runs_project_updates_only_after_selection(self):
        """Project updates run only after user selects packages, then installs selected targets."""
        trace_file = os.path.join(self.tmpdir.name, "trace.log")
        self._setup_test_plugins(trace_file)
        self._setup_mock_system_bins()

        mock_paru = self._write_exec(
            "mock-paru",
            f"""#!/usr/bin/env bash
if [[ -n "${{PARU_SEARCH_SELECT_FILE:-}}" ]]; then
    echo "paru-select:$*" >> "{trace_file}"
    printf 'extra/ripgrep\\n' > "$PARU_SEARCH_SELECT_FILE"
    exit 0
fi
echo "paru-install:$*" >> "{trace_file}"
exit 0
""",
        )

        env = self._base_env()
        env["PARU_BIN"] = mock_paru

        res = subprocess.run(
            [PARU_WRAPPER_PATH, "--searchby", "name", "--aur", "ripgrep"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        with open(trace_file, encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        self.assertEqual(
            lines,
            [
                "paru-select:--searchby name --aur ripgrep",
                "hook:pre-transaction",
                "paru-install:-Quq",
                "paru-install:--pacman /usr/bin/pacman-wrapper -S --searchby name --aur extra/ripgrep",
                "hook:post-transaction",
                "hook:post-transaction-bg",
            ],
        )

    def test_search_install_preserves_aur_target_and_aborts_on_nonzero_select(self):
        """Non-zero exit from selection skips pre-transaction; AUR target selection passes through."""
        trace_file = os.path.join(self.tmpdir.name, "trace.log")
        self._setup_test_plugins(trace_file)
        self._setup_mock_system_bins()

        mock_paru = self._write_exec(
            "mock-paru",
            f"""#!/usr/bin/env bash
if [[ -n "${{PARU_SEARCH_SELECT_FILE:-}}" ]]; then
    printf 'aur/custom-aur-pkg\\n' > "$PARU_SEARCH_SELECT_FILE"
    exit 130
fi
echo "paru-install:$*" >> "{trace_file}"
exit 0
""",
        )

        env = self._base_env()
        env["PARU_BIN"] = mock_paru

        res = subprocess.run(
            [PARU_WRAPPER_PATH, "custom-aur-pkg"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 130, msg=res.stderr)
        self.assertFalse(os.path.exists(trace_file))

        # Now return 0 from selection with aur/custom-aur-pkg
        mock_paru_ok = self._write_exec(
            "mock-paru-ok",
            f"""#!/usr/bin/env bash
if [[ -n "${{PARU_SEARCH_SELECT_FILE:-}}" ]]; then
    printf 'aur/custom-aur-pkg\\n' > "$PARU_SEARCH_SELECT_FILE"
    exit 0
fi
echo "paru-install:$*" >> "{trace_file}"
exit 0
""",
        )
        env["PARU_BIN"] = mock_paru_ok
        res2 = subprocess.run(
            [PARU_WRAPPER_PATH, "custom-aur-pkg"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res2.returncode, 0, msg=res2.stderr)
        with open(trace_file, encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        self.assertIn(
            "paru-install:--pacman /usr/bin/pacman-wrapper -S aur/custom-aur-pkg",
            lines,
        )


class TestParuWrapperSecurityHardening(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.home_dir = os.path.join(self.tmpdir.name, "home")
        self.bin_dir = os.path.join(self.tmpdir.name, "bin")
        self.projects_dir = os.path.join(self.tmpdir.name, "projects")
        os.makedirs(self.home_dir)
        os.makedirs(self.bin_dir)
        os.makedirs(self.projects_dir)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write_exec(self, name, body):
        path = os.path.join(self.bin_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        return path

    def test_verify_cloned_aur_dir_blocks_dangerous_pkg(self):
        """verify_cloned_aur_dir aborts when verify_pkg reports danger > 0."""
        build_dir = os.path.join(self.tmpdir.name, "aur-pkg")
        os.makedirs(build_dir)
        mock_verify = self._write_exec(
            "verify_pkg",
            """#!/usr/bin/env bash
if [[ "${1:-}" == "--json" ]]; then
    echo '{"danger_score":15,"verdict":"SUSPICIOUS","findings":[]}'
    exit 0
fi
echo "Mock verify_pkg report"
exit 1
""",
        )
        env = os.environ.copy()
        env["HOME"] = self.home_dir
        env["NO_COLOR"] = "1"
        env["PATH"] = f"{self.bin_dir}:{env.get('PATH', '')}"
        res = subprocess.run(
            [
                "bash",
                "-c",
                f'source "{PARU_WRAPPER_PATH}"\nverify_cloned_aur_dir "evil-pkg" "{build_dir}"',
            ],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Aborting rebuild", res.stderr)
        self.assertTrue(os.path.exists(mock_verify))

    def test_projects_pull_does_not_source_pkgbuild_and_blocks_on_verify_pkg(self):
        """25-projects-pull.sh parses pkgname safely without executing PKGBUILD and aborts on danger > 0."""
        plugin_path = os.path.join(REPO_DIR, "default-plugins", "25-projects-pull.sh")
        remote_repo = os.path.join(self.tmpdir.name, "remote.git")
        local_repo = os.path.join(self.projects_dir, "demo-pkg")
        pwn_marker = os.path.join(self.tmpdir.name, "pwned")
        makepkg_marker = os.path.join(self.tmpdir.name, "makepkg_ran")

        subprocess.run(["git", "init", "--bare", remote_repo], check=True, capture_output=True)
        subprocess.run(["git", "clone", remote_repo, local_repo], check=True, capture_output=True)
        subprocess.run(["git", "-C", local_repo, "config", "user.email", "t@example.com"], check=True)
        subprocess.run(["git", "-C", local_repo, "config", "user.name", "Test"], check=True)
        with open(os.path.join(local_repo, "PKGBUILD"), "w", encoding="utf-8") as f:
            f.write("pkgname=demo-pkg\npkgver=1.0\npkgrel=1\narch=('any')\n")
        subprocess.run(["git", "-C", local_repo, "add", "PKGBUILD"], check=True)
        subprocess.run(["git", "-C", local_repo, "commit", "-m", "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", local_repo, "push", "origin", "HEAD"], check=True, capture_output=True)

        # Push an upstream commit whose PKGBUILD would execute pwn_marker if sourced
        pusher = os.path.join(self.tmpdir.name, "pusher")
        subprocess.run(["git", "clone", remote_repo, pusher], check=True, capture_output=True)
        subprocess.run(["git", "-C", pusher, "config", "user.email", "t@example.com"], check=True)
        subprocess.run(["git", "-C", pusher, "config", "user.name", "Test"], check=True)
        with open(os.path.join(pusher, "PKGBUILD"), "w", encoding="utf-8") as f:
            f.write(
                f"pkgname=('demo-pkg')\npkgver=1.1\npkgrel=1\narch=('any')\n"
                f"touch '{pwn_marker}'\n"
            )
        subprocess.run(["git", "-C", pusher, "add", "PKGBUILD"], check=True)
        subprocess.run(["git", "-C", pusher, "commit", "-m", "evil"], check=True, capture_output=True)
        subprocess.run(["git", "-C", pusher, "push", "origin", "HEAD"], check=True, capture_output=True)

        self._write_exec(
            "pacman",
            '#!/usr/bin/env bash\nif [[ "${1:-}" == "-Qq" && "${2:-}" == "demo-pkg" ]]; then exit 0; fi\nexit 1\n',
        )
        self._write_exec(
            "makepkg",
            f'#!/usr/bin/env bash\ntouch "{makepkg_marker}"\nexit 0\n',
        )
        self._write_exec(
            "verify_pkg",
            """#!/usr/bin/env bash
if [[ "${1:-}" == "--json" ]]; then
    echo '{"danger_score":15,"verdict":"SUSPICIOUS","findings":[]}'
    exit 0
fi
echo "Suspicious PKGBUILD"
exit 1
""",
        )

        env = os.environ.copy()
        env["HOME"] = self.home_dir
        env["PARU_WRAPPER_PROJECTS_DIR"] = self.projects_dir
        env["PATH"] = f"{self.bin_dir}:{env.get('PATH', '')}"

        res = subprocess.run(
            [
                "bash",
                "-c",
                f'msg_info() {{ echo "$*" >&2; }}\nmsg_warn() {{ echo "WARN: $*" >&2; }}\nsource "{plugin_path}"\nplugin_hook pre-transaction',
            ],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        self.assertFalse(os.path.exists(pwn_marker), "PKGBUILD was executed via source!")
        self.assertFalse(os.path.exists(makepkg_marker), "makepkg ran despite verify_pkg danger > 0!")
        self.assertIn("ORIG_HEAD..HEAD", res.stderr)


class TestParuWrapperRepoSigning(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.home_dir = os.path.join(self.tmpdir.name, "home")
        self.config_dir = os.path.join(self.tmpdir.name, "xdg_config")
        self.plugins_dir = os.path.join(self.config_dir, "paru-wrapper", "plugins.d")
        self.repo_dir = os.path.join(self.tmpdir.name, "repo")
        self.bin_dir = os.path.join(self.tmpdir.name, "bin")
        for d in (self.home_dir, self.plugins_dir, self.repo_dir, self.bin_dir):
            os.makedirs(d)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write_exec(self, name, body):
        path = os.path.join(self.bin_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        return path

    def test_get_repo_sign_flags_reads_makepkg_conf_and_env(self):
        """get_repo_sign_flags includes -s and -k <GPGKEY> from ~/.makepkg.conf or env."""
        with open(os.path.join(self.home_dir, ".makepkg.conf"), "w", encoding="utf-8") as f:
            f.write('GPGKEY="ABC123DEF456"\n')

        env = os.environ.copy()
        env["HOME"] = self.home_dir
        env.pop("GPGKEY", None)
        env.pop("PARU_WRAPPER_GPGKEY", None)

        res = subprocess.run(
            [
                "bash",
                "-c",
                f'source "{PARU_WRAPPER_PATH}"\nflags=()\nget_repo_sign_flags flags\nprintf "%s\\n" "${{flags[@]}}"',
            ],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        self.assertEqual(res.stdout.splitlines(), ["-s", "-k", "ABC123DEF456"])

        env["PARU_WRAPPER_GPGKEY"] = "OVERRIDE999"
        res2 = subprocess.run(
            [
                "bash",
                "-c",
                f'source "{PARU_WRAPPER_PATH}"\nflags=()\nget_repo_sign_flags flags\nprintf "%s\\n" "${{flags[@]}}"',
            ],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res2.returncode, 0, msg=res2.stderr)
        self.assertEqual(res2.stdout.splitlines(), ["-s", "-k", "OVERRIDE999"])

    def test_rebuild_passes_signing_flags_to_repo_remove_and_cleans_sig(self):
        """--rebuild passes -s -k <key> to repo-remove and purges stale .sig files."""
        db_path = os.path.join(self.repo_dir, "MKVPKG.db.tar.gz")
        with open(db_path, "wb") as f:
            f.write(b"")
        stale_pkg = os.path.join(self.repo_dir, "demo-1.0-1-any.pkg.tar.zst")
        stale_sig = f"{stale_pkg}.sig"
        with open(stale_pkg, "wb") as f:
            f.write(b"pkg")
        with open(stale_sig, "wb") as f:
            f.write(b"sig")

        with open(os.path.join(self.home_dir, ".makepkg.conf"), "w", encoding="utf-8") as f:
            f.write('GPGKEY="FPR_TEST_KEY"\n')

        conf_dir = os.path.join(self.home_dir, ".config", "paru-wrapper")
        os.makedirs(conf_dir, exist_ok=True)
        with open(os.path.join(conf_dir, "paru-wrapper.conf"), "w", encoding="utf-8") as f:
            f.write(
                f'PARU_WRAPPER_REPO="MKVPKG"\n'
                f'PARU_WRAPPER_REPO_DB="{db_path}"\n'
                f'PARU_WRAPPER_PROJECTS_DIR="{self.tmpdir.name}/projects"\n'
            )

        for pname in (
            "10-snapper.sh",
            "20-anneal.sh",
            "25-projects-pull.sh",
            "30-rebuild-check.sh",
            "40-paru-completion.sh",
            "50-vault-sync.sh",
        ):
            with open(os.path.join(self.plugins_dir, pname), "w", encoding="utf-8") as f:
                f.write("#!/bin/bash\nplugin_hook() { :; }\n")

        trace_file = os.path.join(self.tmpdir.name, "repo_calls.log")
        self._write_exec(
            "repo-remove",
            f'#!/usr/bin/env bash\necho "repo-remove:$*" >> "{trace_file}"\nexit 0\n',
        )
        self._write_exec("pacman", "#!/usr/bin/env bash\nexit 0\n")
        self._write_exec("sudo", "#!/usr/bin/env bash\nexit 0\n")
        mock_paru = self._write_exec("mock-paru", "#!/usr/bin/env bash\nexit 0\n")

        env = os.environ.copy()
        env["HOME"] = self.home_dir
        env["XDG_CONFIG_HOME"] = self.config_dir
        env["XDG_CACHE_HOME"] = os.path.join(self.tmpdir.name, "cache")
        env["NO_COLOR"] = "1"
        env["PARU_BIN"] = mock_paru
        env["PATH"] = f"{self.bin_dir}:{env.get('PATH', '')}"

        res = subprocess.run(
            [PARU_WRAPPER_PATH, "-S", "--rebuild", "demo"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        self.assertFalse(os.path.exists(stale_pkg))
        self.assertFalse(os.path.exists(stale_sig))
        with open(trace_file, encoding="utf-8") as f:
            self.assertIn(f"repo-remove:-s -k FPR_TEST_KEY -w {db_path} demo", f.read())


class TestParuWrapperRebuildResilience(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.home_dir = os.path.join(self.tmpdir.name, "home")
        self.config_dir = os.path.join(self.tmpdir.name, "xdg_config")
        self.plugins_dir = os.path.join(self.config_dir, "paru-wrapper", "plugins.d")
        self.cache_dir = os.path.join(self.tmpdir.name, "cache")
        self.pkgdest_dir = os.path.join(self.tmpdir.name, "pkgdest")
        self.bin_dir = os.path.join(self.tmpdir.name, "bin")
        for d in (
            self.home_dir,
            self.plugins_dir,
            self.cache_dir,
            self.pkgdest_dir,
            self.bin_dir,
        ):
            os.makedirs(d)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write_exec(self, name, body):
        path = os.path.join(self.bin_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        return path

    def _setup_noop_plugins(self):
        for pname in (
            "10-snapper.sh",
            "20-anneal.sh",
            "25-projects-pull.sh",
            "30-rebuild-check.sh",
            "40-paru-completion.sh",
            "50-vault-sync.sh",
        ):
            with open(os.path.join(self.plugins_dir, pname), "w", encoding="utf-8") as f:
                f.write("#!/bin/bash\nplugin_hook() { :; }\n")

    def _base_env(self):
        env = os.environ.copy()
        env["HOME"] = self.home_dir
        env["XDG_CONFIG_HOME"] = self.config_dir
        env["XDG_CACHE_HOME"] = self.cache_dir
        env["NO_COLOR"] = "1"
        env["PATH"] = f"{self.bin_dir}:{env.get('PATH', '')}"
        return env

    def test_fetch_aur_metadata_batch_caches_pkgbase(self):
        """fetch_aur_metadata_batch stores both Version and PackageBase for split AUR packages."""
        self._write_exec(
            "curl",
            """#!/usr/bin/env bash
cat << 'JSON'
{"version":5,"type":"multiinfo","resultcount":1,"results":[{"Name":"caelestia-sddm-locklike-git","PackageBase":"caelestia-sddm-git","Version":"r185.6c8ceff-1"}]}
JSON
""",
        )
        res = subprocess.run(
            [
                "bash",
                "-c",
                (
                    f'source "{PARU_WRAPPER_PATH}"\n'
                    'fetch_aur_metadata_batch "caelestia-sddm-locklike-git"\n'
                    'echo "${_aur_pkgs_cache[caelestia-sddm-locklike-git]}|${_aur_pkgbase_cache[caelestia-sddm-locklike-git]}"'
                ),
            ],
            env=self._base_env(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        self.assertEqual(res.stdout.strip(), "r185.6c8ceff-1|caelestia-sddm-git")

    def test_rebuild_skips_repo_remove_when_repo_db_empty(self):
        """--rebuild without PARU_WRAPPER_REPO_DB must not invoke repo-remove."""
        self._setup_noop_plugins()
        trace_file = os.path.join(self.tmpdir.name, "calls.log")
        self._write_exec(
            "repo-remove",
            f'#!/usr/bin/env bash\necho "repo-remove:$*" >> "{trace_file}"\nexit 1\n',
        )
        self._write_exec("pacman", "#!/usr/bin/env bash\nexit 0\n")
        self._write_exec("sudo", "#!/usr/bin/env bash\nexit 0\n")
        self._write_exec("curl", '#!/usr/bin/env bash\necho \'{"results":[]}\'\n')
        mock_paru = self._write_exec("mock-paru", "#!/usr/bin/env bash\nexit 0\n")

        env = self._base_env()
        env["PARU_BIN"] = mock_paru
        res = subprocess.run(
            [PARU_WRAPPER_PATH, "-S", "--rebuild", "demo"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        self.assertFalse(os.path.exists(trace_file))
        self.assertNotIn("Usage: repo-remove", res.stdout + res.stderr)

    def test_force_rebuild_continues_when_verify_pkg_flags_one_package(self):
        """Security verification failure skips the flagged package without aborting remaining batch targets."""
        self._setup_noop_plugins()
        trace_file = os.path.join(self.tmpdir.name, "rebuild.log")
        with open(os.path.join(self.plugins_dir, "20-anneal.sh"), "w", encoding="utf-8") as f:
            f.write(
                f'#!/bin/bash\nplugin_hook() {{ [ "$1" = "package-rebuilt" ] && echo "rebuilt:$2" >> "{trace_file}"; }}\n'
            )

        self._write_exec("pacman", "#!/usr/bin/env bash\nexit 0\n")
        self._write_exec("sudo", "#!/usr/bin/env bash\nexit 0\n")
        self._write_exec(
            "curl",
            """#!/usr/bin/env bash
cat << 'JSON'
{"results":[
  {"Name":"bad-pkg","PackageBase":"bad-pkg","Version":"1.0-1"},
  {"Name":"good-pkg","PackageBase":"good-pkg","Version":"1.0-1"}
]}
JSON
""",
        )
        self._write_exec(
            "git",
            f"""#!/usr/bin/env bash
if [[ "$1" == "clone" ]]; then
    url="$4"
    dest="$5"
    mkdir -p "$dest"
    pkg=$(basename "$url" .git)
    printf 'pkgname=%s\\npkgver=1.0\\npkgrel=1\\n' "$pkg" > "$dest/PKGBUILD"
    echo "clone:$pkg" >> "{trace_file}"
    exit 0
fi
exit 0
""",
        )
        self._write_exec(
            "verify_pkg",
            """#!/usr/bin/env bash
target="${@: -1}"
if grep -q "pkgname=bad-pkg" "$target/PKGBUILD" 2>/dev/null; then
    if [[ "${1:-}" == "--json" ]]; then
        echo '{"danger_score":25,"verdict":"CRITICAL_RISK","findings":[]}'
        exit 0
    fi
    echo "Flagged bad-pkg"
    exit 2
fi
if [[ "${1:-}" == "--json" ]]; then
    echo '{"danger_score":0,"verdict":"CLEAN","findings":[]}'
fi
exit 0
""",
        )
        self._write_exec(
            "makepkg",
            f"""#!/usr/bin/env bash
if [[ "$*" == *"--packagelist"* ]]; then
    exit 0
fi
pkg=$(awk -F= '/^pkgname=/{{print $2}}' PKGBUILD)
echo "makepkg:$pkg:$*" >> "{trace_file}"
exit 0
""",
        )
        mock_paru = self._write_exec("mock-paru", "#!/usr/bin/env bash\nexit 0\n")

        env = self._base_env()
        env["PARU_BIN"] = mock_paru
        res = subprocess.run(
            [PARU_WRAPPER_PATH, "-S", "--rebuild", "bad-pkg", "good-pkg"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 1, msg=res.stderr)
        with open(trace_file, encoding="utf-8") as f:
            log = f.read()
        self.assertIn("clone:bad-pkg", log)
        self.assertIn("clone:good-pkg", log)
        self.assertIn("makepkg:good-pkg:-Csfi --noconfirm", log)
        self.assertIn("rebuilt:good-pkg", log)
        self.assertNotIn("makepkg:bad-pkg", log)
        self.assertNotIn("rebuilt:bad-pkg", log)

    def test_force_rebuild_clones_package_base_and_installs_only_requested_split_pkg(self):
        """Split AUR targets clone PackageBase, build without -i, and install only the requested subpackage."""
        self._setup_noop_plugins()
        trace_file = os.path.join(self.tmpdir.name, "split.log")
        lock_pkg = os.path.join(self.pkgdest_dir, "caelestia-sddm-locklike-git-1-1-any.pkg.tar.zst")
        min_pkg = os.path.join(self.pkgdest_dir, "caelestia-sddm-minimalist-git-1-1-any.pkg.tar.zst")

        self._write_exec(
            "curl",
            """#!/usr/bin/env bash
cat << 'JSON'
{"results":[
  {"Name":"caelestia-sddm-locklike-git","PackageBase":"caelestia-sddm-git","Version":"r185-1"}
]}
JSON
""",
        )
        self._write_exec(
            "git",
            f"""#!/usr/bin/env bash
if [[ "$1" == "clone" ]]; then
    url="$4"
    dest="$5"
    echo "clone:$url" >> "{trace_file}"
    if [[ "$url" == *"/caelestia-sddm-git.git" ]]; then
        mkdir -p "$dest"
        printf 'pkgbase=caelestia-sddm-git\\npkgname=(caelestia-sddm-locklike-git caelestia-sddm-minimalist-git)\\n' > "$dest/PKGBUILD"
        exit 0
    fi
    exit 1
fi
exit 0
""",
        )
        self._write_exec(
            "verify_pkg",
            """#!/usr/bin/env bash
if [[ "${1:-}" == "--json" ]]; then
    echo '{"danger_score":0,"verdict":"CLEAN","findings":[]}'
fi
exit 0
""",
        )
        self._write_exec(
            "makepkg",
            f"""#!/usr/bin/env bash
if [[ "$*" == *"--packagelist"* ]]; then
    printf '%s\\n%s\\n' "{lock_pkg}" "{min_pkg}"
    exit 0
fi
echo "makepkg:$*" >> "{trace_file}"
touch "{lock_pkg}" "{min_pkg}"
exit 0
""",
        )
        self._write_exec(
            "pacman",
            f"""#!/usr/bin/env bash
if [[ "${{1:-}}" == "-Qp" ]]; then
    b=$(basename "$2")
    if [[ "$b" == caelestia-sddm-locklike-git-* ]]; then
        echo "caelestia-sddm-locklike-git 1-1"
    elif [[ "$b" == caelestia-sddm-minimalist-git-* ]]; then
        echo "caelestia-sddm-minimalist-git 1-1"
    fi
    exit 0
fi
if [[ "${{1:-}}" == "-U" ]]; then
    echo "pacman:$*" >> "{trace_file}"
    exit 0
fi
exit 0
""",
        )
        self._write_exec(
            "sudo",
            f"""#!/usr/bin/env bash
echo "sudo:$*" >> "{trace_file}"
"$@"
""",
        )
        mock_paru = self._write_exec("mock-paru", "#!/usr/bin/env bash\nexit 0\n")

        env = self._base_env()
        env["PARU_BIN"] = mock_paru
        res = subprocess.run(
            [PARU_WRAPPER_PATH, "-S", "--rebuild", "caelestia-sddm-locklike-git"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        with open(trace_file, encoding="utf-8") as f:
            log = f.read()
        self.assertIn("clone:https://aur.archlinux.org/caelestia-sddm-git.git", log)
        self.assertIn("makepkg:-Csf --noconfirm", log)
        self.assertNotIn("makepkg:-Csfi", log)
        self.assertNotIn("makepkg:-sfi", log)
        self.assertIn(f"pacman:-U --noconfirm -- {lock_pkg}", log)
        self.assertNotIn(min_pkg, log)
        self.assertTrue(os.path.exists(lock_pkg))
        self.assertFalse(os.path.exists(min_pkg))

    def test_rebuild_check_plugin_skips_inside_anneal_session(self):
        """30-rebuild-check.sh skips recursive rebuild-check while inside an anneal session."""
        plugin_path = os.path.join(REPO_DIR, "default-plugins", "30-rebuild-check.sh")
        marker = os.path.join(self.tmpdir.name, "rebuild_check_called")
        self._write_exec(
            "rebuild-check",
            f'#!/usr/bin/env bash\ntouch "{marker}"\nexit 0\n',
        )
        self._write_exec("sudo", '#!/usr/bin/env bash\n"$@"\n')
        res = subprocess.run(
            [
                "bash",
                "-c",
                f'msg_info() {{ :; }}\nis_anneal=true\nsource "{plugin_path}"\nplugin_hook deferred-hooks pkg1',
            ],
            env=self._base_env(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        self.assertFalse(os.path.exists(marker))

    def test_force_rebuild_local_project_uses_cleanbuild_and_prepare_failure_retries_with_cleanbuild(self):
        """--rebuild passes -Csfi for local projects, and prepare()/build() failure retries once with -C."""
        self._setup_noop_plugins()
        projects_dir = os.path.join(self.tmpdir.name, "projects")
        pkg_dir = os.path.join(projects_dir, "local-aria2-git")
        os.makedirs(pkg_dir)
        with open(os.path.join(pkg_dir, "PKGBUILD"), "w", encoding="utf-8") as f:
            f.write("pkgname=local-aria2-git\npkgver=1.0\npkgrel=1\narch=('any')\n")

        trace_file = os.path.join(self.tmpdir.name, "local_makepkg.log")
        self._write_exec("pacman", "#!/usr/bin/env bash\nexit 0\n")
        self._write_exec("sudo", "#!/usr/bin/env bash\nexit 0\n")
        self._write_exec("curl", '#!/usr/bin/env bash\necho \'{"results":[]}\'\n')
        self._write_exec(
            "makepkg",
            f"""#!/usr/bin/env bash
echo "makepkg:$*" >> "{trace_file}"
exit 0
""",
        )
        mock_paru = self._write_exec("mock-paru", "#!/usr/bin/env bash\nexit 0\n")

        env = self._base_env()
        env["PARU_BIN"] = mock_paru
        env["PARU_WRAPPER_PROJECTS_DIR"] = projects_dir
        res = subprocess.run(
            [PARU_WRAPPER_PATH, "-S", "--rebuild", "local-aria2-git"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        with open(trace_file, encoding="utf-8") as f:
            self.assertIn("makepkg:-Csfi --noconfirm", f.read())

        # Now test run_makepkg_with_recovery retrying with -C after a prepare() failure
        retry_calls = os.path.join(self.tmpdir.name, "retry_calls")
        self._write_exec(
            "makepkg",
            f"""#!/usr/bin/env bash
count=0
[[ -f "{retry_calls}" ]] && count=$(cat "{retry_calls}")
count=$((count + 1))
echo "$count" > "{retry_calls}"
echo "makepkg:$*" >> "{trace_file}"
if [[ $count -eq 1 ]]; then
    echo "live stdout line"
    echo "autopoint: File m4/nls.m4 has been locally modified." >&2
    echo "==> ERROR: A failure occurred in prepare()." >&2
    exit 4
fi
echo "cleanbuild retry ok"
exit 0
""",
        )
        env["PARU_WRAPPER_NET_CHECK_CMD"] = "true"
        res2 = subprocess.run(
            [
                "bash",
                "-c",
                f'source "{PARU_WRAPPER_PATH}"\nrun_makepkg_with_recovery "{pkg_dir}" -sfi --noconfirm',
            ],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res2.returncode, 0, msg=res2.stderr)
        self.assertIn("live stdout line", res2.stdout)
        self.assertIn("cleanbuild retry ok", res2.stdout)
        self.assertIn("Retrying with -C (--cleanbuild)", res2.stderr)
        with open(trace_file, encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        self.assertIn("makepkg:-sfi --noconfirm", lines)
        self.assertIn("makepkg:-C -sfi --noconfirm", lines)

    def test_stale_srcdest_clone_auto_recovery_and_retry(self):
        """makepkg '<srcdest>/pkg is not a clone of <url>' deletes verified SRCDEST dir and retries once."""
        self._setup_noop_plugins()
        srcdest_dir = os.path.join(self.tmpdir.name, "srcdest")
        stale_clone = os.path.join(srcdest_dir, "chromecastize")
        os.makedirs(os.path.join(stale_clone, "objects"))
        with open(os.path.join(stale_clone, "FETCH_HEAD"), "w", encoding="utf-8") as f:
            f.write("")

        trace_file = os.path.join(self.tmpdir.name, "srcdest_trace.log")
        calls_file = os.path.join(self.tmpdir.name, "srcdest_calls")
        self._write_exec("pacman", "#!/usr/bin/env bash\nexit 0\n")
        self._write_exec("sudo", "#!/usr/bin/env bash\nexit 0\n")
        self._write_exec(
            "curl",
            """#!/usr/bin/env bash
cat << 'JSON'
{"results":[{"Name":"chromecastize-git","PackageBase":"chromecastize-git","Version":"59.c739cec-1"}]}
JSON
""",
        )
        self._write_exec(
            "git",
            """#!/usr/bin/env bash
if [[ "$1" == "clone" ]]; then
    dest="$5"
    mkdir -p "$dest"
    printf 'pkgname=chromecastize-git\\npkgver=1\\npkgrel=1\\n' > "$dest/PKGBUILD"
    exit 0
fi
exit 0
""",
        )
        self._write_exec(
            "verify_pkg",
            '#!/usr/bin/env bash\n[[ "${1:-}" == "--json" ]] && echo \'{"danger_score":0,"verdict":"CLEAN","findings":[]}\'\nexit 0\n',
        )
        self._write_exec(
            "makepkg",
            f"""#!/usr/bin/env bash
if [[ "$*" == *"--packagelist"* ]]; then
    exit 0
fi
count=0
[[ -f "{calls_file}" ]] && count=$(cat "{calls_file}")
count=$((count + 1))
echo "$count" > "{calls_file}"
echo "makepkg:$count:$*" >> "{trace_file}"
echo "==> Making package: chromecastize-git"
if [[ $count -eq 1 ]]; then
    printf '\\033[1;31m==> ERROR:\\033[0m\\033(B %s is not a clone of https://github.com/bc-petrkotek/chromecastize.git\\n' "{stale_clone}" >&2
    exit 17
fi
echo "==> Finished making: chromecastize-git"
exit 0
""",
        )
        mock_paru = self._write_exec("mock-paru", "#!/usr/bin/env bash\nexit 0\n")

        env = self._base_env()
        env["PARU_BIN"] = mock_paru
        env["PARU_WRAPPER_SRCDEST"] = srcdest_dir
        env["PARU_WRAPPER_NET_CHECK_CMD"] = "true"
        res = subprocess.run(
            [PARU_WRAPPER_PATH, "-S", "--rebuild", "chromecastize-git"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        self.assertFalse(os.path.exists(stale_clone))
        self.assertIn("Detected stale/mismatched SRCDEST git clone", res.stderr)
        self.assertIn("==> Making package: chromecastize-git", res.stdout)
        self.assertIn("==> Finished making: chromecastize-git", res.stdout)
        with open(calls_file, encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "2")
        with open(trace_file, encoding="utf-8") as f:
            log = f.read()
        self.assertIn("makepkg:1:-Csfi --noconfirm", log)
        self.assertIn("makepkg:2:-Csfi --noconfirm", log)

    def test_stale_srcdest_recovery_refuses_outside_dir_and_caps_at_one_retry(self):
        """Safety guards refuse to delete paths outside SRCDEST and stop after one SRCDEST retry."""
        srcdest_dir = os.path.join(self.tmpdir.name, "srcdest")
        outside_dir = os.path.join(self.tmpdir.name, "outside-repo")
        build_dir = os.path.join(self.tmpdir.name, "build-dir")
        os.makedirs(srcdest_dir)
        os.makedirs(os.path.join(outside_dir, "objects"))
        os.makedirs(build_dir)

        calls_file = os.path.join(self.tmpdir.name, "outside_calls")
        self._write_exec(
            "makepkg",
            f"""#!/usr/bin/env bash
count=0
[[ -f "{calls_file}" ]] && count=$(cat "{calls_file}")
echo $((count + 1)) > "{calls_file}"
echo "==> ERROR: {outside_dir} is not a clone of https://example.com/repo.git" >&2
exit 17
""",
        )
        env = self._base_env()
        env["PARU_WRAPPER_SRCDEST"] = srcdest_dir
        env["PARU_WRAPPER_NET_CHECK_CMD"] = "true"

        res = subprocess.run(
            [
                "bash",
                "-c",
                f'source "{PARU_WRAPPER_PATH}"\nrun_makepkg_with_recovery "{build_dir}" -Csfi --noconfirm',
            ],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 17)
        self.assertTrue(os.path.exists(outside_dir), "Must never delete directories outside SRCDEST")
        self.assertIn("Refusing to auto-remove", res.stderr)
        with open(calls_file, encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "1")

        # Now point inside SRCDEST and verify persistent failure stops after 1 retry (2 total attempts)
        inside_dir = os.path.join(srcdest_dir, "nheko-git")
        os.makedirs(os.path.join(inside_dir, "objects"))
        calls_file2 = os.path.join(self.tmpdir.name, "cap_calls")
        self._write_exec(
            "makepkg",
            f"""#!/usr/bin/env bash
count=0
[[ -f "{calls_file2}" ]] && count=$(cat "{calls_file2}")
echo $((count + 1)) > "{calls_file2}"
mkdir -p "{inside_dir}/objects"
echo "==> ERROR: {inside_dir} is not a clone of https://example.com/nheko.git" >&2
exit 17
""",
        )
        res2 = subprocess.run(
            [
                "bash",
                "-c",
                f'source "{PARU_WRAPPER_PATH}"\nrun_makepkg_with_recovery "{build_dir}" -Csfi --noconfirm',
            ],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res2.returncode, 17)
        with open(calls_file2, encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "2")


class TestParuWrapperLowPriority(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.home_dir = os.path.join(self.tmpdir.name, "home")
        self.config_dir = os.path.join(self.tmpdir.name, "xdg_config")
        self.plugins_dir = os.path.join(self.config_dir, "paru-wrapper", "plugins.d")
        self.cache_dir = os.path.join(self.tmpdir.name, "cache")
        self.bin_dir = os.path.join(self.tmpdir.name, "bin")
        for d in (self.home_dir, self.plugins_dir, self.cache_dir, self.bin_dir):
            os.makedirs(d, exist_ok=True)
        for pname in (
            "10-snapper.sh",
            "20-anneal.sh",
            "25-projects-pull.sh",
            "30-rebuild-check.sh",
            "40-paru-completion.sh",
            "50-vault-sync.sh",
        ):
            with open(os.path.join(self.plugins_dir, pname), "w", encoding="utf-8") as f:
                f.write("#!/usr/bin/env bash\nplugin_hook() { :; }\n")

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write_exec(self, name, body):
        path = os.path.join(self.bin_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        return path

    def _base_env(self):
        env = os.environ.copy()
        env["HOME"] = self.home_dir
        env["XDG_CONFIG_HOME"] = self.config_dir
        env["XDG_CACHE_HOME"] = self.cache_dir
        env["NO_COLOR"] = "1"
        env["PARU_CLONE_DIR"] = os.path.join(self.tmpdir.name, "clone")
        env["PARU_WRAPPER_NET_CHECK_CMD"] = "true"
        env["PATH"] = f"{self.bin_dir}:{env.get('PATH', '')}"
        os.makedirs(env["PARU_CLONE_DIR"], exist_ok=True)
        return env

    def _install_priority_mocks(self, trace_file, systemd_probe_rc=0, include_ionice=True):
        self._write_exec(
            "pacman",
            """#!/usr/bin/env bash
if [[ "${1:-}" == "-Si" ]]; then
    printf 'Repository      : extra\\nName            : ripgrep\\n'
    exit 0
fi
exit 0
""",
        )
        self._write_exec("sudo", "#!/usr/bin/env bash\nexit 0\n")
        self._write_exec("curl", '#!/usr/bin/env bash\necho \'{"results":[]}\'\n')
        self._write_exec(
            "systemd-run",
            f"""#!/usr/bin/env bash
if [[ "$*" == *"true"* ]]; then
    exit {systemd_probe_rc}
fi
echo "systemd-run:$*" >> "{trace_file}"
while [[ $# -gt 0 ]]; do
    if [[ "$1" == "--" ]]; then
        shift
        break
    fi
    shift
done
exec "$@"
""",
        )
        self._write_exec(
            "nice",
            f"""#!/usr/bin/env bash
echo "nice:$*" >> "{trace_file}"
while [[ $# -gt 0 ]]; do
    if [[ "$1" == "--" ]]; then
        shift
        break
    fi
    shift
done
exec "$@"
""",
        )
        if include_ionice:
            self._write_exec(
                "ionice",
                f"""#!/usr/bin/env bash
echo "ionice:$*" >> "{trace_file}"
while [[ $# -gt 0 ]]; do
    if [[ "$1" == "--" ]]; then
        shift
        break
    fi
    shift
done
exec "$@"
""",
            )
        return self._write_exec(
            "mock-paru",
            f"""#!/usr/bin/env bash
if [[ "${{1:-}}" == "-Quq" ]]; then
    exit 0
fi
echo "paru:$*" >> "{trace_file}"
exit 0
""",
        )

    def test_default_uses_systemd_run_scope_and_strips_no_extra_args(self):
        """By default PARU_WRAPPER_LOW_PRIORITY wraps paru in systemd-run user scope."""
        trace_file = os.path.join(self.tmpdir.name, "trace.log")
        mock_paru = self._install_priority_mocks(trace_file, systemd_probe_rc=0)
        env = self._base_env()
        env["PARU_BIN"] = mock_paru

        res = subprocess.run(
            [PARU_WRAPPER_PATH, "-S", "ripgrep"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        with open(trace_file, encoding="utf-8") as f:
            log = f.read()
        self.assertIn("systemd-run:--user --scope -q -p CPUWeight=20 -p IOWeight=20 -- nice -n 15 ionice -c 3 --", log)
        self.assertIn("paru:--pacman /usr/bin/pacman-wrapper -S ripgrep", log)

    def test_fallback_to_nice_ionice_when_systemd_run_fails(self):
        """When systemd-run --user --scope probe fails, falls back to nice -n 15 ionice -c 3."""
        trace_file = os.path.join(self.tmpdir.name, "trace.log")
        mock_paru = self._install_priority_mocks(trace_file, systemd_probe_rc=1)
        env = self._base_env()
        env["PARU_BIN"] = mock_paru

        res = subprocess.run(
            [PARU_WRAPPER_PATH, "-S", "ripgrep"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        with open(trace_file, encoding="utf-8") as f:
            log = f.read()
        self.assertNotIn("systemd-run:", log)
        self.assertIn("nice:-n 15 ionice -c 3 --", log)
        self.assertIn("paru:--pacman /usr/bin/pacman-wrapper -S ripgrep", log)

    def test_fallback_to_nice_only_when_ionice_unavailable(self):
        """When systemd-run fails and ionice is unavailable, falls back to nice -n 15 --."""
        trace_file = os.path.join(self.tmpdir.name, "trace.log")
        mock_paru = self._install_priority_mocks(trace_file, systemd_probe_rc=1, include_ionice=False)

        # Build a restricted PATH dir without system ionice so command -v ionice fails
        restricted_bin = os.path.join(self.tmpdir.name, "restricted_bin")
        os.makedirs(restricted_bin, exist_ok=True)
        for tool in os.listdir(self.bin_dir):
            os.symlink(os.path.join(self.bin_dir, tool), os.path.join(restricted_bin, tool))
        for sys_tool in ("bash", "env", "mktemp", "rm", "cat", "grep", "awk", "sed", "tr", "find", "stat", "dirname", "basename", "readlink", "mkdir", "touch", "id", "sleep"):
            for sys_dir in ("/usr/bin", "/bin"):
                candidate = os.path.join(sys_dir, sys_tool)
                if os.path.exists(candidate) and not os.path.exists(os.path.join(restricted_bin, sys_tool)):
                    os.symlink(candidate, os.path.join(restricted_bin, sys_tool))
                    break

        env = self._base_env()
        env["PARU_BIN"] = mock_paru
        env["PATH"] = restricted_bin

        res = subprocess.run(
            [PARU_WRAPPER_PATH, "-S", "ripgrep"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        with open(trace_file, encoding="utf-8") as f:
            log = f.read()
        self.assertNotIn("systemd-run:", log)
        self.assertNotIn("ionice:", log)
        self.assertIn("nice:-n 15 --", log)
        self.assertIn("paru:--pacman /usr/bin/pacman-wrapper -S ripgrep", log)

    def test_no_low_priority_flag_disables_wrapping_and_is_stripped(self):
        """--no-low-priority runs paru directly without throttling and is stripped from forwarded args."""
        trace_file = os.path.join(self.tmpdir.name, "trace.log")
        mock_paru = self._install_priority_mocks(trace_file, systemd_probe_rc=0)
        env = self._base_env()
        env["PARU_BIN"] = mock_paru

        res = subprocess.run(
            [PARU_WRAPPER_PATH, "--no-low-priority", "-S", "ripgrep"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        with open(trace_file, encoding="utf-8") as f:
            log = f.read()
        self.assertNotIn("systemd-run:", log)
        self.assertNotIn("nice:", log)
        self.assertNotIn("ionice:", log)
        self.assertNotIn("--no-low-priority", log)
        self.assertIn("paru:--pacman /usr/bin/pacman-wrapper -S ripgrep", log)

    def test_env_false_disables_and_low_priority_flag_reenables_and_is_stripped(self):
        """PARU_WRAPPER_LOW_PRIORITY=false disables wrapping; --low-priority re-enables and is stripped."""
        trace_file = os.path.join(self.tmpdir.name, "trace.log")
        mock_paru = self._install_priority_mocks(trace_file, systemd_probe_rc=0)
        env = self._base_env()
        env["PARU_BIN"] = mock_paru
        env["PARU_WRAPPER_LOW_PRIORITY"] = "false"

        res_off = subprocess.run(
            [PARU_WRAPPER_PATH, "-S", "ripgrep"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_off.returncode, 0, msg=res_off.stderr)
        with open(trace_file, encoding="utf-8") as f:
            log_off = f.read()
        self.assertNotIn("systemd-run:", log_off)
        self.assertNotIn("nice:", log_off)
        self.assertIn("paru:--pacman /usr/bin/pacman-wrapper -S ripgrep", log_off)

        with open(trace_file, "w", encoding="utf-8") as f:
            f.write("")

        res_on = subprocess.run(
            [PARU_WRAPPER_PATH, "--low-priority", "-S", "ripgrep"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_on.returncode, 0, msg=res_on.stderr)
        with open(trace_file, encoding="utf-8") as f:
            log_on = f.read()
        self.assertIn("systemd-run:--user --scope -q -p CPUWeight=20 -p IOWeight=20 -- nice -n 15 ionice -c 3 --", log_on)
        self.assertNotIn("--low-priority", log_on)
        self.assertIn("paru:--pacman /usr/bin/pacman-wrapper -S ripgrep", log_on)

    def test_makepkg_invocation_respects_low_priority_toggle(self):
        """run_makepkg_with_recovery wraps makepkg by default and skips wrapping when PARU_WRAPPER_LOW_PRIORITY=false."""
        trace_file = os.path.join(self.tmpdir.name, "makepkg_prio.log")
        self._install_priority_mocks(trace_file, systemd_probe_rc=0)
        build_dir = os.path.join(self.tmpdir.name, "build")
        os.makedirs(build_dir, exist_ok=True)
        self._write_exec(
            "makepkg",
            f'#!/usr/bin/env bash\necho "makepkg:$*" >> "{trace_file}"\nexit 0\n',
        )

        env = self._base_env()
        res_on = subprocess.run(
            ["bash", "-c", f'source "{PARU_WRAPPER_PATH}"\nrun_makepkg_with_recovery "{build_dir}" -Csfi --noconfirm'],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_on.returncode, 0, msg=res_on.stderr)
        with open(trace_file, encoding="utf-8") as f:
            log_on = f.read()
        self.assertIn("systemd-run:", log_on)
        self.assertIn("makepkg:-Csfi --noconfirm", log_on)

        with open(trace_file, "w", encoding="utf-8") as f:
            f.write("")
        env["PARU_WRAPPER_LOW_PRIORITY"] = "false"
        res_off = subprocess.run(
            ["bash", "-c", f'source "{PARU_WRAPPER_PATH}"\nrun_makepkg_with_recovery "{build_dir}" -Csfi --noconfirm'],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_off.returncode, 0, msg=res_off.stderr)
        with open(trace_file, encoding="utf-8") as f:
            log_off = f.read()
        self.assertNotIn("systemd-run:", log_off)
        self.assertNotIn("nice:", log_off)
        self.assertIn("makepkg:-Csfi --noconfirm", log_off)

    def test_dry_run_with_low_priority_flags_strips_flags(self):
        """--dry-run strips --low-priority and --no-low-priority from reported paru commands."""
        trace_file = os.path.join(self.tmpdir.name, "dry.log")
        mock_paru = self._install_priority_mocks(trace_file, systemd_probe_rc=0)
        env = self._base_env()
        env["PARU_BIN"] = mock_paru

        for flag in ("--no-low-priority", "--low-priority"):
            res = subprocess.run(
                [PARU_WRAPPER_PATH, "--dry-run", flag, "-S", "ripgrep"],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, msg=res.stderr)
            self.assertIn("DRY RUN: would run: /usr/bin/paru --pacman /usr/bin/pacman-wrapper -S ripgrep", res.stderr)
            self.assertNotIn(flag, res.stderr)
        self.assertFalse(os.path.exists(trace_file))


class TestParuWrapperReliabilityAndWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.home_dir = os.path.join(self.tmpdir.name, "home")
        self.config_dir = os.path.join(self.tmpdir.name, "xdg_config")
        self.plugins_dir = os.path.join(self.config_dir, "paru-wrapper", "plugins.d")
        self.cache_dir = os.path.join(self.tmpdir.name, "cache")
        self.state_dir = os.path.join(self.tmpdir.name, "state")
        self.clone_dir = os.path.join(self.tmpdir.name, "clone")
        self.pkgdest_dir = os.path.join(self.tmpdir.name, "pkgdest")
        self.projects_dir = os.path.join(self.tmpdir.name, "projects")
        self.hooks_dir = os.path.join(self.tmpdir.name, "etc-hooks")
        self.sys_hooks_dir = os.path.join(self.tmpdir.name, "libalpm-hooks")
        self.pid_file = os.path.join(self.tmpdir.name, "hooks.pid")
        self.bin_dir = os.path.join(self.tmpdir.name, "bin")
        for d in (
            self.home_dir,
            self.plugins_dir,
            self.cache_dir,
            self.state_dir,
            self.clone_dir,
            self.pkgdest_dir,
            self.projects_dir,
            self.hooks_dir,
            self.sys_hooks_dir,
            self.bin_dir,
        ):
            os.makedirs(d, exist_ok=True)
        for pname in (
            "10-snapper.sh",
            "20-anneal.sh",
            "25-projects-pull.sh",
            "30-rebuild-check.sh",
            "40-paru-completion.sh",
            "50-vault-sync.sh",
        ):
            with open(os.path.join(self.plugins_dir, pname), "w", encoding="utf-8") as f:
                f.write("#!/usr/bin/env bash\nplugin_hook() { :; }\n")

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write_exec(self, name, body):
        path = os.path.join(self.bin_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        return path

    def _base_env(self):
        env = os.environ.copy()
        env["HOME"] = self.home_dir
        env["XDG_CONFIG_HOME"] = self.config_dir
        env["XDG_CACHE_HOME"] = self.cache_dir
        env["XDG_STATE_HOME"] = os.path.join(self.home_dir, ".local", "state")
        env["NO_COLOR"] = "1"
        env["PARU_CLONE_DIR"] = self.clone_dir
        env["PARU_WRAPPER_PROJECTS_DIR"] = self.projects_dir
        env["PARU_WRAPPER_STATE_DIR"] = self.state_dir
        env["PARU_WRAPPER_HOOKS_DIR"] = self.hooks_dir
        env["PARU_WRAPPER_SYSTEM_HOOKS_DIR"] = self.sys_hooks_dir
        env["PARU_WRAPPER_HOOKS_PID_FILE"] = self.pid_file
        env["PARU_WRAPPER_NET_CHECK_CMD"] = "true"
        env["PARU_WRAPPER_NET_WAIT_TIMEOUT"] = "2"
        env["PARU_WRAPPER_NET_POLL_INTERVAL"] = "1"
        env["PARU_WRAPPER_NET_RETRY_MAX"] = "2"
        env["PARU_WRAPPER_RETRY_DELAY"] = "0"
        env["PARU_WRAPPER_LOW_PRIORITY"] = "false"
        env["PATH"] = f"{self.bin_dir}:{env.get('PATH', '')}"
        return env

    def test_fetch_aur_metadata_batch_retries_transient_error_and_handles_outage(self):
        """Transient curl/DNS failure retries via network recovery; permanent outage avoids 'not in AUR' falsehood."""
        curl_calls = os.path.join(self.tmpdir.name, "curl_calls")
        self._write_exec(
            "curl",
            f"""#!/usr/bin/env bash
c=0
[[ -f "{curl_calls}" ]] && c=$(cat "{curl_calls}")
c=$((c + 1))
echo "$c" > "{curl_calls}"
if [[ $c -eq 1 ]]; then
    exit 6
fi
echo '{{"version":5,"type":"multiinfo","results":[{{"Name":"demo-aur","PackageBase":"demo-aur","Version":"2.0-1","MakeDepends":["scdoc>=1.0"]}}]}}'
""",
        )
        env = self._base_env()
        res = subprocess.run(
            [
                "bash",
                "-c",
                f'source "{PARU_WRAPPER_PATH}"\nfetch_aur_metadata_batch "demo-aur"\necho "${{_aur_rpc_failed}}|${{_aur_pkgs_cache[demo-aur]}}|${{_aur_makedepends_cache[demo-aur]}}"',
            ],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        self.assertEqual(res.stdout.strip(), "0|2.0-1|scdoc")

        # Now make curl fail permanently and ensure paru-wrapper -S does not claim "not in the AUR"
        trace_file = os.path.join(self.tmpdir.name, "paru_trace.log")
        self._write_exec("curl", "#!/usr/bin/env bash\nexit 6\n")
        self._write_exec("pacman", "#!/usr/bin/env bash\nexit 0\n")
        self._write_exec("sudo", "#!/usr/bin/env bash\nexit 0\n")
        mock_paru = self._write_exec(
            "mock-paru",
            f'#!/usr/bin/env bash\necho "paru:$*" >> "{trace_file}"\nexit 0\n',
        )
        env["PARU_BIN"] = mock_paru
        res2 = subprocess.run(
            [PARU_WRAPPER_PATH, "-S", "aur-only-pkg"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res2.returncode, 0, msg=res2.stderr)
        self.assertNotIn("is not in the AUR", res2.stderr)
        self.assertIn("AUR RPC lookup failed", res2.stderr)
        with open(trace_file, encoding="utf-8") as f:
            self.assertIn("paru:--pacman /usr/bin/pacman-wrapper -S aur-only-pkg", f.read())

    def test_verify_pkg_allows_safe_local_idiom_and_respects_auto_accept(self):
        """SAFE_LOCAL_IDIOM / ACCEPT verdicts pass; SUSPICIOUS respects PARU_WRAPPER_PKGSCAN_AUTO_ACCEPT_DANGER."""
        build_dir = os.path.join(self.tmpdir.name, "pkgdir")
        os.makedirs(build_dir, exist_ok=True)
        verdict_file = os.path.join(self.tmpdir.name, "verdict.json")
        self._write_exec(
            "verify_pkg",
            f"""#!/usr/bin/env bash
if [[ "${{1:-}}" == "--json" ]]; then
    cat "{verdict_file}"
    exit 0
fi
echo "report"
exit 0
""",
        )
        env = self._base_env()

        # 1. SAFE_LOCAL_IDIOM with Danger: 1 and recommended_action: ACCEPT -> allowed
        with open(verdict_file, "w", encoding="utf-8") as f:
            f.write('{"danger_score":1,"verdict":"SAFE_LOCAL_IDIOM","recommended_action":"ACCEPT","findings":[]}')
        res_idiom = subprocess.run(
            ["bash", "-c", f'source "{PARU_WRAPPER_PATH}"\nverify_cloned_aur_dir "linux-cachyos-bore" "{build_dir}"'],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_idiom.returncode, 0, msg=res_idiom.stderr)

        # 2. SUSPICIOUS -> blocked when AUTO_ACCEPT_DANGER=0, allowed when =1
        with open(verdict_file, "w", encoding="utf-8") as f:
            f.write('{"danger_score":12,"verdict":"SUSPICIOUS","recommended_action":"REVIEW_MANUALLY","findings":[]}')
        res_susp_block = subprocess.run(
            ["bash", "-c", f'source "{PARU_WRAPPER_PATH}"\nverify_cloned_aur_dir "weird-pkg" "{build_dir}"'],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res_susp_block.returncode, 0)

        env_auto = dict(env)
        env_auto["PARU_WRAPPER_PKGSCAN_AUTO_ACCEPT_DANGER"] = "1"
        res_susp_ok = subprocess.run(
            ["bash", "-c", f'source "{PARU_WRAPPER_PATH}"\nverify_cloned_aur_dir "weird-pkg" "{build_dir}"'],
            env=env_auto,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_susp_ok.returncode, 0, msg=res_susp_ok.stderr)

        # 3. CRITICAL_RISK -> always blocked even with AUTO_ACCEPT_DANGER=1
        with open(verdict_file, "w", encoding="utf-8") as f:
            f.write('{"danger_score":30,"verdict":"CRITICAL_RISK","recommended_action":"REJECT","findings":[]}')
        res_crit = subprocess.run(
            ["bash", "-c", f'source "{PARU_WRAPPER_PATH}"\nverify_cloned_aur_dir "evil-pkg" "{build_dir}"'],
            env=env_auto,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res_crit.returncode, 0)

        # 4. 25-projects-pull.sh allows SAFE_LOCAL_IDIOM
        plugin_path = os.path.join(REPO_DIR, "default-plugins", "25-projects-pull.sh")
        remote_repo = os.path.join(self.tmpdir.name, "remote-bore.git")
        local_repo = os.path.join(self.projects_dir, "linux-cachyos-bore")
        makepkg_marker = os.path.join(self.tmpdir.name, "bore_built")
        subprocess.run(["git", "init", "--bare", remote_repo], check=True, capture_output=True)
        subprocess.run(["git", "clone", remote_repo, local_repo], check=True, capture_output=True)
        subprocess.run(["git", "-C", local_repo, "config", "user.email", "t@example.com"], check=True)
        subprocess.run(["git", "-C", local_repo, "config", "user.name", "Test"], check=True)
        with open(os.path.join(local_repo, "PKGBUILD"), "w", encoding="utf-8") as f:
            f.write("pkgname=linux-cachyos-bore\npkgver=1.0\npkgrel=1\narch=('x86_64')\n")
        subprocess.run(["git", "-C", local_repo, "add", "PKGBUILD"], check=True)
        subprocess.run(["git", "-C", local_repo, "commit", "-m", "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", local_repo, "push", "origin", "HEAD"], check=True, capture_output=True)

        pusher = os.path.join(self.tmpdir.name, "pusher-bore")
        subprocess.run(["git", "clone", remote_repo, pusher], check=True, capture_output=True)
        subprocess.run(["git", "-C", pusher, "config", "user.email", "t@example.com"], check=True)
        subprocess.run(["git", "-C", pusher, "config", "user.name", "Test"], check=True)
        with open(os.path.join(pusher, "PKGBUILD"), "w", encoding="utf-8") as f:
            f.write("pkgname=linux-cachyos-bore\npkgver=1.1\npkgrel=1\narch=('x86_64')\n")
        subprocess.run(["git", "-C", pusher, "add", "PKGBUILD"], check=True)
        subprocess.run(["git", "-C", pusher, "commit", "-m", "bump"], check=True, capture_output=True)
        subprocess.run(["git", "-C", pusher, "push", "origin", "HEAD"], check=True, capture_output=True)

        with open(verdict_file, "w", encoding="utf-8") as f:
            f.write('{"danger_score":1,"verdict":"SAFE_LOCAL_IDIOM","recommended_action":"ACCEPT","findings":[]}')
        self._write_exec("pacman", '#!/usr/bin/env bash\n[[ "${1:-}" == "-Qq" ]] && exit 0\nexit 1\n')
        self._write_exec("makepkg", f'#!/usr/bin/env bash\ntouch "{makepkg_marker}"\nexit 0\n')
        res_plug = subprocess.run(
            [
                "bash",
                "-c",
                f'msg_info() {{ echo "$*" >&2; }}\nmsg_warn() {{ echo "WARN: $*" >&2; }}\nsource "{plugin_path}"\nplugin_hook pre-transaction',
            ],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_plug.returncode, 0, msg=res_plug.stderr)
        self.assertTrue(os.path.exists(makepkg_marker), "25-projects-pull.sh should build SAFE_LOCAL_IDIOM packages!")

    def test_orphan_cleanup_preserves_builddeps_by_default_and_toggles_with_flag(self):
        """Orphan cleanup preserves rustup/cmake/target makedeps by default and removes them with --cleanup-builddeps."""
        trace_file = os.path.join(self.tmpdir.name, "orphan_trace.log")
        self._write_exec(
            "curl",
            """#!/usr/bin/env bash
cat << 'JSON'
{"results":[{"Name":"target-aur","PackageBase":"target-aur","Version":"1.0-1","MakeDepends":["custom-makedep"]}]}
JSON
""",
        )
        self._write_exec(
            "pacman",
            f"""#!/usr/bin/env bash
if [[ "${{1:-}}" == "-Qtdq" ]]; then
    printf 'rustup\\ncmake\\nghc\\ncustom-makedep\\ntrue-orphan\\n'
    exit 0
fi
if [[ "${{1:-}}" == "-Rns" ]]; then
    echo "pacman-Rns:$*" >> "{trace_file}"
    exit 0
fi
exit 0
""",
        )
        self._write_exec("sudo", '#!/usr/bin/env bash\n"$@"\n')
        mock_paru = self._write_exec(
            "mock-paru",
            f"""#!/usr/bin/env bash
if [[ "${{1:-}}" == "-Quq" ]]; then
    exit 0
fi
echo "paru:$*" >> "{trace_file}"
exit 0
""",
        )
        env = self._base_env()
        env["PARU_BIN"] = mock_paru

        # Default (PARU_WRAPPER_CLEANUP_BUILDDEPS=0): preserve rustup, cmake, ghc, custom-makedep
        res_def = subprocess.run(
            [PARU_WRAPPER_PATH, "-S", "target-aur"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_def.returncode, 0, msg=res_def.stderr)
        with open(trace_file, encoding="utf-8") as f:
            log_def = f.read()
        self.assertIn("pacman-Rns:-Rns --noconfirm -- true-orphan", log_def)
        self.assertNotIn("rustup", log_def)
        self.assertNotIn("custom-makedep", log_def)

        # --cleanup-builddeps removes all orphans and strips flag before forwarding to paru
        with open(trace_file, "w", encoding="utf-8") as f:
            f.write("")
        res_clean = subprocess.run(
            [PARU_WRAPPER_PATH, "--cleanup-builddeps", "-S", "target-aur"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_clean.returncode, 0, msg=res_clean.stderr)
        with open(trace_file, encoding="utf-8") as f:
            log_clean = f.read()
        self.assertIn("pacman-Rns:-Rns --noconfirm -- rustup cmake ghc custom-makedep true-orphan", log_clean)
        self.assertNotIn("--cleanup-builddeps", log_clean)

        # --no-cleanup-builddeps overrides PARU_WRAPPER_CLEANUP_BUILDDEPS=1
        with open(trace_file, "w", encoding="utf-8") as f:
            f.write("")
        env_on = dict(env)
        env_on["PARU_WRAPPER_CLEANUP_BUILDDEPS"] = "1"
        res_override = subprocess.run(
            [PARU_WRAPPER_PATH, "--no-cleanup-builddeps", "-S", "target-aur"],
            env=env_on,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_override.returncode, 0, msg=res_override.stderr)
        with open(trace_file, encoding="utf-8") as f:
            log_ovr = f.read()
        self.assertIn("pacman-Rns:-Rns --noconfirm -- true-orphan", log_ovr)
        self.assertNotIn("rustup", log_ovr)
        self.assertNotIn("--no-cleanup-builddeps", log_ovr)

    def test_hook_pid_lock_prevents_mid_transaction_reenable_and_restores_stale(self):
        """Live owner PID keeps heavy hooks (including fnm-update/list-orphans/postz-grub) masked; dead PID restores."""
        sys_hooks = (
            "05-snap-pac-pre.hook",
            "zz-snap-pac-post.hook",
            "zz-snap-pac-postz-grub.hook",
            "paru-completion-update.hook",
            "rebuild-check.hook",
            "list-orphans.hook",
        )
        for h in sys_hooks:
            with open(os.path.join(self.sys_hooks_dir, h), "w", encoding="utf-8") as f:
                f.write("[Trigger]\nTarget = *\n")
        fnm_hook = os.path.join(self.hooks_dir, "fnm-update.hook")
        with open(fnm_hook, "w", encoding="utf-8") as f:
            f.write("[Action]\nDescription = fnm\n")

        self._write_exec("pacman", "#!/usr/bin/env bash\nexit 0\n")
        self._write_exec("sudo", '#!/usr/bin/env bash\n"$@"\n')
        mock_paru = self._write_exec("mock-paru", "#!/usr/bin/env bash\nexit 0\n")
        env = self._base_env()
        env["PARU_BIN"] = mock_paru

        # Start a live background owner process so its PID stays alive during nested paru-wrapper calls
        owner_proc = subprocess.Popen(["sleep", "30"])
        self.addCleanup(lambda: (owner_proc.terminate(), owner_proc.wait()))

        # Disable hooks using _disable_pacman_hooks, then overwrite pid_file with live owner_proc.pid
        res_dis = subprocess.run(
            ["bash", "-c", f'source "{PARU_WRAPPER_PATH}"\n_disable_pacman_hooks'],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_dis.returncode, 0, msg=res_dis.stderr)
        with open(self.pid_file, "w", encoding="utf-8") as f:
            f.write(f"{owner_proc.pid}\n")

        for h in sys_hooks + ("fnm-update.hook",):
            p = os.path.join(self.hooks_dir, h)
            self.assertTrue(os.path.islink(p), f"{h} should be symlinked")
            self.assertEqual(os.readlink(p), "/dev/null")
        self.assertTrue(os.path.isfile(f"{fnm_hook}.paru-wrapper-disabled"))

        # Nested invocation (simulating paru-completion-update.service running paru -Pc) must NOT re-enable hooks
        res_nested = subprocess.run(
            [PARU_WRAPPER_PATH, "-Pc"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_nested.returncode, 0, msg=res_nested.stderr)
        for h in sys_hooks + ("fnm-update.hook",):
            self.assertTrue(os.path.islink(os.path.join(self.hooks_dir, h)))

        # Terminate owner process so PID is dead -> next invocation must restore all hooks including fnm-update.hook
        owner_proc.terminate()
        owner_proc.wait()
        res_stale = subprocess.run(
            [PARU_WRAPPER_PATH, "-Pc"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_stale.returncode, 0, msg=res_stale.stderr)
        self.assertIn("Detected stale disabled hooks", res_stale.stderr)
        for h in sys_hooks:
            self.assertFalse(os.path.exists(os.path.join(self.hooks_dir, h)))
        self.assertFalse(os.path.islink(fnm_hook))
        self.assertTrue(os.path.isfile(fnm_hook))
        self.assertFalse(os.path.exists(f"{fnm_hook}.paru-wrapper-disabled"))
        self.assertFalse(os.path.exists(self.pid_file))

    def test_force_rebuild_batches_pacman_u_and_supports_fallback_and_no_batch(self):
        """FORCE_REBUILD builds with -Csf, skips -debug, runs one batched pacman -U, and falls back / honors --no-batch."""
        trace_file = os.path.join(self.tmpdir.name, "batch.log")
        with open(os.path.join(self.plugins_dir, "20-anneal.sh"), "w", encoding="utf-8") as f:
            f.write(f'#!/bin/bash\nplugin_hook() {{ [ "$1" = "package-rebuilt" ] && echo "rebuilt:$2" >> "{trace_file}"; }}\n')

        pkg_a = os.path.join(self.pkgdest_dir, "pkg-alpha-1.0-1-x86_64.pkg.tar.zst")
        pkg_a_dbg = os.path.join(self.pkgdest_dir, "pkg-alpha-debug-1.0-1-x86_64.pkg.tar.zst")
        pkg_b = os.path.join(self.pkgdest_dir, "pkg-beta-1.0-1-x86_64.pkg.tar.zst")

        self._write_exec(
            "curl",
            """#!/usr/bin/env bash
cat << 'JSON'
{"results":[
  {"Name":"pkg-alpha","PackageBase":"pkg-alpha","Version":"1.0-1"},
  {"Name":"pkg-beta","PackageBase":"pkg-beta","Version":"1.0-1"}
]}
JSON
""",
        )
        self._write_exec(
            "git",
            """#!/usr/bin/env bash
if [[ "$1" == "clone" ]]; then
    url="$4"; dest="$5"
    mkdir -p "$dest"
    pkg=$(basename "$url" .git)
    printf 'pkgname=%s\\npkgver=1.0\\npkgrel=1\\n' "$pkg" > "$dest/PKGBUILD"
fi
exit 0
""",
        )
        self._write_exec("verify_pkg", '#!/usr/bin/env bash\n[[ "${1:-}" == "--json" ]] && echo \'{"danger_score":0,"verdict":"CLEAN"}\'\nexit 0\n')
        self._write_exec(
            "makepkg",
            f"""#!/usr/bin/env bash
pkg=$(awk -F= '/^pkgname=/{{print $2}}' PKGBUILD)
if [[ "$*" == *"--packagelist"* ]]; then
    if [[ "$pkg" == "pkg-alpha" ]]; then
        printf '%s\\n%s\\n' "{pkg_a}" "{pkg_a_dbg}"
    else
        printf '%s\\n' "{pkg_b}"
    fi
    exit 0
fi
echo "makepkg:$pkg:$*" >> "{trace_file}"
if [[ "$pkg" == "pkg-alpha" ]]; then
    touch "{pkg_a}" "{pkg_a_dbg}"
else
    touch "{pkg_b}"
fi
exit 0
""",
        )
        fail_batch_flag = os.path.join(self.tmpdir.name, "fail_batch")
        self._write_exec(
            "pacman",
            f"""#!/usr/bin/env bash
if [[ "${{1:-}}" == "-Qp" ]]; then
    b=$(basename "$2")
    case "$b" in
        pkg-alpha-debug-*) echo "pkg-alpha-debug 1.0-1" ;;
        pkg-alpha-*) echo "pkg-alpha 1.0-1" ;;
        pkg-beta-*) echo "pkg-beta 1.0-1" ;;
    esac
    exit 0
fi
if [[ "${{1:-}}" == "-U" ]]; then
    echo "pacman-U:$*" >> "{trace_file}"
    if [[ -f "{fail_batch_flag}" && $# -gt 4 ]]; then
        exit 1
    fi
    exit 0
fi
exit 0
""",
        )
        self._write_exec("sudo", '#!/usr/bin/env bash\n"$@"\n')
        mock_paru = self._write_exec("mock-paru", "#!/usr/bin/env bash\nexit 0\n")

        env = self._base_env()
        env["PARU_BIN"] = mock_paru
        res = subprocess.run(
            [PARU_WRAPPER_PATH, "-S", "--rebuild", "pkg-alpha", "pkg-beta"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        with open(trace_file, encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        self.assertIn("makepkg:pkg-alpha:-Csf --noconfirm", lines)
        self.assertIn("makepkg:pkg-beta:-Csf --noconfirm", lines)
        u_lines = [ln for ln in lines if ln.startswith("pacman-U:")]
        self.assertEqual(len(u_lines), 1, msg=lines)
        self.assertIn(pkg_a, u_lines[0])
        self.assertIn(pkg_b, u_lines[0])
        self.assertNotIn(pkg_a_dbg, u_lines[0])
        self.assertIn("rebuilt:pkg-alpha", lines)
        self.assertIn("rebuilt:pkg-beta", lines)

        # Test batch failure falls back to per-package pacman -U
        with open(trace_file, "w", encoding="utf-8") as f:
            f.write("")
        with open(fail_batch_flag, "w", encoding="utf-8") as f:
            f.write("1")
        res_fb = subprocess.run(
            [PARU_WRAPPER_PATH, "-S", "--rebuild", "pkg-alpha", "pkg-beta"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_fb.returncode, 0, msg=res_fb.stderr)
        with open(trace_file, encoding="utf-8") as f:
            fb_lines = [ln.strip() for ln in f if ln.strip()]
        fb_u = [ln for ln in fb_lines if ln.startswith("pacman-U:")]
        self.assertEqual(len(fb_u), 3, msg=fb_lines)
        self.assertIn("Batched pacman -U failed; falling back to per-package installation", res_fb.stderr)

        # Test --no-batch installs individually and strips flag
        os.remove(fail_batch_flag)
        with open(trace_file, "w", encoding="utf-8") as f:
            f.write("")
        res_nb = subprocess.run(
            [PARU_WRAPPER_PATH, "--no-batch", "-S", "--rebuild", "pkg-alpha", "pkg-beta"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_nb.returncode, 0, msg=res_nb.stderr)
        with open(trace_file, encoding="utf-8") as f:
            nb_lines = [ln.strip() for ln in f if ln.strip()]
        self.assertIn("makepkg:pkg-beta:-Csfi --noconfirm", nb_lines)

    def test_git_fallback_and_haskell_preflight_plus_retry_on_new_commit(self):
        """Broken -git build runs Haskell ghc-pkg check, falls back to release pkg, and retries on newer commit."""
        trace_file = os.path.join(self.tmpdir.name, "git_fb.log")
        remote_commit_file = os.path.join(self.tmpdir.name, "remote_commit")
        fail_git_build_file = os.path.join(self.tmpdir.name, "fail_git_build")
        with open(remote_commit_file, "w", encoding="utf-8") as f:
            f.write("1111111111111111111111111111111111111111")
        with open(fail_git_build_file, "w", encoding="utf-8") as f:
            f.write("1")

        pkg_file = os.path.join(self.pkgdest_dir, "shellcheck-git-1-1-x86_64.pkg.tar.zst")
        self._write_exec(
            "curl",
            """#!/usr/bin/env bash
cat << 'JSON'
{"results":[{"Name":"shellcheck-git","PackageBase":"shellcheck-git","Version":"r100-1"}]}
JSON
""",
        )
        self._write_exec(
            "git",
            f"""#!/usr/bin/env bash
if [[ "$1" == "clone" ]]; then
    dest="$5"
    mkdir -p "$dest"
    cat > "$dest/PKGBUILD" << 'PB'
pkgname=shellcheck-git
pkgver=1.0
pkgrel=1
makedepends=('ghc' 'cabal-install')
source=('git+https://example.com/shellcheck.git')
PB
    exit 0
fi
if [[ "$1" == "ls-remote" ]]; then
    sha=$(cat "{remote_commit_file}")
    printf '%s\\tHEAD\\n' "${{sha}}"
    exit 0
fi
exit 0
""",
        )
        self._write_exec("verify_pkg", '#!/usr/bin/env bash\n[[ "${1:-}" == "--json" ]] && echo \'{"danger_score":0,"verdict":"CLEAN"}\'\nexit 0\n')
        self._write_exec(
            "ghc-pkg",
            f"""#!/usr/bin/env bash
echo "ghc-pkg:$*" >> "{trace_file}"
echo "broken-haskell-pkg-0.1"
exit 1
""",
        )
        self._write_exec(
            "makepkg",
            f"""#!/usr/bin/env bash
if [[ "$*" == *"--packagelist"* ]]; then
    echo "{pkg_file}"
    exit 0
fi
echo "makepkg:$*" >> "{trace_file}"
if [[ -f "{fail_git_build_file}" ]]; then
    exit 4
fi
touch "{pkg_file}"
exit 0
""",
        )
        self._write_exec(
            "pacman",
            f"""#!/usr/bin/env bash
if [[ "${{1:-}}" == "-Si" && "${{2:-}}" == "shellcheck" ]]; then
    printf 'Repository      : extra\\nName            : shellcheck\\n'
    exit 0
fi
if [[ "${{1:-}}" == "-Qp" ]]; then
    echo "shellcheck-git 1-1"
    exit 0
fi
if [[ "${{1:-}}" == "-S" || "${{1:-}}" == "-U" ]]; then
    echo "pacman:$*" >> "{trace_file}"
    exit 0
fi
exit 0
""",
        )
        self._write_exec("sudo", '#!/usr/bin/env bash\n"$@"\n')
        mock_paru = self._write_exec(
            "mock-paru",
            f'#!/usr/bin/env bash\n[[ "${{1:-}}" == "-Quq" ]] && exit 0\necho "paru:$*" >> "{trace_file}"\nexit 0\n',
        )

        env = self._base_env()
        env["PARU_BIN"] = mock_paru
        res = subprocess.run(
            [PARU_WRAPPER_PATH, "-S", "--rebuild", "shellcheck-git"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        self.assertIn("ghc-pkg check --simple-output", res.stderr)
        self.assertIn("broken-haskell-pkg-0.1", res.stderr)
        self.assertIn("Fallback: 'shellcheck-git' failed at commit 1111111111111111111111111111111111111111; installing official release package 'shellcheck' instead.", res.stderr)

        tsv_path = os.path.join(self.state_dir, "git-fallbacks.tsv")
        self.assertTrue(os.path.isfile(tsv_path))
        with open(tsv_path, encoding="utf-8") as f:
            row = f.read().strip().split("\t")
        self.assertEqual(len(row), 4)
        self.assertEqual(row[:3], ["shellcheck-git", "shellcheck", "1111111111111111111111111111111111111111"])

        # Subsequent -Syu with SAME commit does NOT retry shellcheck-git
        with open(trace_file, "w", encoding="utf-8") as f:
            f.write("")
        res_same = subprocess.run([PARU_WRAPPER_PATH, "-Syu"], env=env, capture_output=True, text=True)
        self.assertEqual(res_same.returncode, 0, msg=res_same.stderr)
        self.assertIn("No new commit yet for fallback 'shellcheck-git'", res_same.stderr)
        with open(trace_file, encoding="utf-8") as f:
            self.assertNotIn("makepkg:", f.read())

        # Subsequent -Syu with NEW commit retries shellcheck-git, succeeds, and clears fallback entry
        with open(remote_commit_file, "w", encoding="utf-8") as f:
            f.write("2222222222222222222222222222222222222222")
        os.remove(fail_git_build_file)
        with open(trace_file, "w", encoding="utf-8") as f:
            f.write("")
        res_retry = subprocess.run([PARU_WRAPPER_PATH, "-Syu"], env=env, capture_output=True, text=True)
        self.assertEqual(res_retry.returncode, 0, msg=res_retry.stderr)
        self.assertIn("New commit available for 'shellcheck-git'", res_retry.stderr)
        self.assertIn("Removing fallback entry", res_retry.stderr)
        self.assertFalse(os.path.exists(tsv_path))
        with open(trace_file, encoding="utf-8") as f:
            log_retry = f.read()
        self.assertIn("makepkg:-Csf --noconfirm", log_retry)
        self.assertIn(f"pacman:-U --needed -- {pkg_file}", log_retry)

    def test_git_fallback_to_aur_release_and_no_haskell_warning_for_non_haskell(self):
        """Non-official -git failure falls back to AUR release pkg; non-Haskell PKGBUILDs skip ghc-pkg check."""
        trace_file = os.path.join(self.tmpdir.name, "aur_fb.log")
        rel_pkg_file = os.path.join(self.pkgdest_dir, "custom-tool-1.0-1-x86_64.pkg.tar.zst")

        self._write_exec(
            "curl",
            """#!/usr/bin/env bash
if [[ "$*" == *"custom-tool-git"* ]]; then
    echo '{"results":[{"Name":"custom-tool-git","PackageBase":"custom-tool-git","Version":"r10-1"}]}'
else
    echo '{"results":[{"Name":"custom-tool","PackageBase":"custom-tool","Version":"1.0-1"}]}'
fi
""",
        )
        self._write_exec(
            "git",
            """#!/usr/bin/env bash
if [[ "$1" == "clone" ]]; then
    url="$4"; dest="$5"
    mkdir -p "$dest"
    pkg=$(basename "$url" .git)
    if [[ "$pkg" == "custom-tool-git" ]]; then
        printf 'pkgname=custom-tool-git\\npkgver=1\\npkgrel=1\\nsource=("git+https://example.com/custom-tool.git")\\n' > "$dest/PKGBUILD"
    else
        printf 'pkgname=custom-tool\\npkgver=1.0\\npkgrel=1\\n' > "$dest/PKGBUILD"
    fi
    exit 0
fi
if [[ "$1" == "ls-remote" ]]; then
    printf 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeef\\tHEAD\\n'
    exit 0
fi
exit 0
""",
        )
        self._write_exec("verify_pkg", '#!/usr/bin/env bash\n[[ "${1:-}" == "--json" ]] && echo \'{"danger_score":0,"verdict":"CLEAN"}\'\nexit 0\n')
        self._write_exec("ghc-pkg", f'#!/usr/bin/env bash\necho "ghc-pkg-called" >> "{trace_file}"\nexit 1\n')
        self._write_exec(
            "makepkg",
            f"""#!/usr/bin/env bash
pkg=$(awk -F= '/^pkgname=/{{print $2}}' PKGBUILD)
if [[ "$*" == *"--packagelist"* ]]; then
    if [[ "$pkg" == "custom-tool" ]]; then
        echo "{rel_pkg_file}"
    else
        echo "{self.pkgdest_dir}/custom-tool-git-1-1-x86_64.pkg.tar.zst"
    fi
    exit 0
fi
echo "makepkg:$pkg:$*" >> "{trace_file}"
if [[ "$pkg" == "custom-tool-git" ]]; then
    exit 4
fi
touch "{rel_pkg_file}"
exit 0
""",
        )
        self._write_exec(
            "pacman",
            f"""#!/usr/bin/env bash
if [[ "${{1:-}}" == "-Si" ]]; then
    exit 1
fi
if [[ "${{1:-}}" == "-Qp" ]]; then
    echo "custom-tool 1.0-1"
    exit 0
fi
if [[ "${{1:-}}" == "-U" ]]; then
    echo "pacman-U:$*" >> "{trace_file}"
    exit 0
fi
exit 0
""",
        )
        self._write_exec("sudo", '#!/usr/bin/env bash\n"$@"\n')
        mock_paru = self._write_exec("mock-paru", "#!/usr/bin/env bash\nexit 0\n")

        env = self._base_env()
        env["PARU_BIN"] = mock_paru
        res = subprocess.run(
            [PARU_WRAPPER_PATH, "-S", "--rebuild", "custom-tool-git"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        self.assertIn("installing AUR release package 'custom-tool' instead", res.stderr)
        with open(trace_file, encoding="utf-8") as f:
            log = f.read()
        self.assertNotIn("ghc-pkg-called", log)
        self.assertIn("makepkg:custom-tool:-Csf --noconfirm", log)
        self.assertIn(f"pacman-U:-U --needed -- {rel_pkg_file}", log)
        tsv_path = os.path.join(self.state_dir, "git-fallbacks.tsv")
        self.assertTrue(os.path.isfile(tsv_path))
        with open(tsv_path, encoding="utf-8") as f:
            row = f.read().strip().split("\t")
        self.assertEqual(row[:3], ["custom-tool-git", "custom-tool", "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"])


if __name__ == "__main__":
    unittest.main()

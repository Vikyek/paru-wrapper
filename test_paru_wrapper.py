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


if __name__ == "__main__":
    unittest.main()

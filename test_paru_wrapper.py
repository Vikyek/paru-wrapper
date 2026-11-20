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


if __name__ == "__main__":
    unittest.main()

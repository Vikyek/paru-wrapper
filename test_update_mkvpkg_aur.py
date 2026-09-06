import unittest
from unittest.mock import patch, MagicMock
import subprocess
import urllib.request
import json
import update_mkvpkg_aur

class TestUpdateMkvpkgAur(unittest.TestCase):

    def setUp(self):
        update_mkvpkg_aur.clear_installed_cache()

    def tearDown(self):
        update_mkvpkg_aur.clear_installed_cache()

    @patch('update_mkvpkg_aur.subprocess.check_output')
    def test_run_cmd_success(self, mock_check_output):
        mock_check_output.return_value = "output\n"
        result = update_mkvpkg_aur.run_cmd(["echo", "output"])
        self.assertEqual(result, "output")
        mock_check_output.assert_called_once_with(["echo", "output"], text=True)

    @patch('update_mkvpkg_aur.subprocess.check_output')
    def test_run_cmd_failure(self, mock_check_output):
        mock_check_output.side_effect = subprocess.CalledProcessError(1, ["cmd"])
        result = update_mkvpkg_aur.run_cmd(["cmd"])
        self.assertEqual(result, "")
        mock_check_output.assert_called_once_with(["cmd"], text=True)

    @patch('update_mkvpkg_aur.subprocess.check_output')
    def test_run_cmd_file_not_found(self, mock_check_output):
        mock_check_output.side_effect = FileNotFoundError("Command not found")
        result = update_mkvpkg_aur.run_cmd(["cmd"])
        self.assertEqual(result, "")
        mock_check_output.assert_called_once_with(["cmd"], text=True)

    @patch('update_mkvpkg_aur.subprocess.check_output')
    def test_run_cmd_subprocess_error(self, mock_check_output):
        mock_check_output.side_effect = subprocess.SubprocessError("Subprocess error")
        result = update_mkvpkg_aur.run_cmd(["cmd"])
        self.assertEqual(result, "")
        mock_check_output.assert_called_once_with(["cmd"], text=True)

    @patch('update_mkvpkg_aur.subprocess.check_output')
    def test_run_cmd_os_error(self, mock_check_output):
        mock_check_output.side_effect = PermissionError("Permission denied")
        result = update_mkvpkg_aur.run_cmd(["cmd"])
        self.assertEqual(result, "")
        mock_check_output.assert_called_once_with(["cmd"], text=True)

    @patch('update_mkvpkg_aur.subprocess.run')
    def test_is_installed_true(self, mock_run):
        mock_run.return_value = MagicMock(stdout="pkg\notherpkg\n")
        self.assertTrue(update_mkvpkg_aur.is_installed("pkg"))
        mock_run.assert_called_once_with(["pacman", "-Qq"], capture_output=True, text=True, check=True)

    @patch('update_mkvpkg_aur.subprocess.run')
    def test_is_installed_false(self, mock_run):
        mock_run.return_value = MagicMock(stdout="otherpkg\n")
        self.assertFalse(update_mkvpkg_aur.is_installed("pkg"))
        mock_run.assert_called_once_with(["pacman", "-Qq"], capture_output=True, text=True, check=True)

    @patch('update_mkvpkg_aur.subprocess.run')
    def test_is_installed_empty_cache_no_fallback(self, mock_run):
        # Edge case: Bulk pacman -Qq returns empty output (0 packages installed)
        mock_run.return_value = MagicMock(stdout="")
        self.assertFalse(update_mkvpkg_aur.is_installed("pkg1"))
        self.assertFalse(update_mkvpkg_aur.is_installed("pkg2"))
        # Must call pacman -Qq bulk query ONLY ONCE, without falling back to single query
        mock_run.assert_called_once_with(["pacman", "-Qq"], capture_output=True, text=True, check=True)

    @patch('update_mkvpkg_aur.subprocess.run')
    def test_is_installed_bulk_exception_fallback(self, mock_run):
        # Edge case: Bulk query raises exception, falls back to per-package query
        def run_side_effect(cmd, **kwargs):
            if cmd == ["pacman", "-Qq"]:
                raise subprocess.CalledProcessError(1, cmd)
            if cmd == ["pacman", "-Qq", "pkg1"]:
                return MagicMock(returncode=0)
            return MagicMock(returncode=1)

        mock_run.side_effect = run_side_effect
        self.assertTrue(update_mkvpkg_aur.is_installed("pkg1"))
        self.assertFalse(update_mkvpkg_aur.is_installed("pkg2"))

    @patch.object(update_mkvpkg_aur, 'repo_name', 'testrepo')
    @patch('update_mkvpkg_aur.run_cmd')
    def test_get_mkvpkg_packages_and_versions(self, mock_run_cmd):
        mock_run_cmd.return_value = "testrepo pkg1 1.0\ntestrepo pkg2 2.0\notherrepo pkg3 3.0"
        expected = {"pkg1": "1.0", "pkg2": "2.0"}
        self.assertEqual(update_mkvpkg_aur.get_mkvpkg_packages_and_versions(), expected)
        mock_run_cmd.assert_called_once_with(["pacman", "-Sl", "testrepo"])

    @patch.object(update_mkvpkg_aur, 'repo_name', '')
    @patch('update_mkvpkg_aur.run_cmd')
    def test_get_mkvpkg_packages_and_versions_empty(self, mock_run_cmd):
        self.assertEqual(update_mkvpkg_aur.get_mkvpkg_packages_and_versions(), {})
        mock_run_cmd.assert_not_called()

    @patch.object(update_mkvpkg_aur, 'repo_name', 'testrepo')
    @patch('update_mkvpkg_aur.run_cmd')
    def test_get_mkvpkg_packages_and_versions_empty_output(self, mock_run_cmd):
        mock_run_cmd.return_value = ""
        self.assertEqual(update_mkvpkg_aur.get_mkvpkg_packages_and_versions(), {})
        mock_run_cmd.assert_called_once_with(["pacman", "-Sl", "testrepo"])

    @patch.object(update_mkvpkg_aur, 'repo_name', 'testrepo')
    @patch('update_mkvpkg_aur.run_cmd')
    def test_get_mkvpkg_packages_and_versions_malformed_output(self, mock_run_cmd):
        # Line 1: Malformed (too few parts)
        # Line 2: Wrong repo
        # Line 3: Correct
        mock_run_cmd.return_value = "testrepo pkg1\notherrepo pkg2 2.0\ntestrepo pkg3 3.0"
        expected = {"pkg3": "3.0"}
        self.assertEqual(update_mkvpkg_aur.get_mkvpkg_packages_and_versions(), expected)
        mock_run_cmd.assert_called_once_with(["pacman", "-Sl", "testrepo"])

    @patch('update_mkvpkg_aur.subprocess.run')
    def test_is_installed_file_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError("Command not found")
        self.assertFalse(update_mkvpkg_aur.is_installed("pkg"))

    @patch('update_mkvpkg_aur.urllib.request.urlopen')
    def test_query_aur_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "results": [{"Name": "pkg1", "Version": "1.1"}]
        }).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        expected = {"pkg1": "1.1"}
        self.assertEqual(update_mkvpkg_aur.query_aur(["pkg1"]), expected)

        # Verify request URL construction & timeout
        req = mock_urlopen.call_args[0][0]
        self.assertIn("https://aur.archlinux.org/rpc/?v=5&type=info", req.full_url)
        self.assertIn("arg%5B%5D=pkg1", req.full_url)
        self.assertEqual(mock_urlopen.call_args[1].get("timeout"), 10)

    @patch('update_mkvpkg_aur.urllib.request.urlopen')
    def test_query_aur_batching(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"results": []}).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Test batching over 50 packages (e.g. 75 packages = 2 requests)
        pkgs = [f"pkg{i}" for i in range(75)]
        update_mkvpkg_aur.query_aur(pkgs)
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch('update_mkvpkg_aur.urllib.request.urlopen')
    def test_query_aur_failure(self, mock_urlopen):
        import urllib.error
        import http.client
        import json

        # URLError
        mock_urlopen.side_effect = urllib.error.URLError("Network error")
        with self.assertRaises(RuntimeError):
            update_mkvpkg_aur.query_aur(["pkg1"])

        # TimeoutError
        mock_urlopen.side_effect = TimeoutError("Request timed out")
        with self.assertRaises(RuntimeError):
            update_mkvpkg_aur.query_aur(["pkg1"])

        # HTTPException
        mock_urlopen.side_effect = http.client.IncompleteRead(b"")
        with self.assertRaises(RuntimeError):
            update_mkvpkg_aur.query_aur(["pkg1"])

        # UnicodeDecodeError / JSONDecodeError
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"\xff\xfe\xfd"
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        with self.assertRaises(RuntimeError):
            update_mkvpkg_aur.query_aur(["pkg1"])

        # JSONDecodeError
        mock_resp.read.return_value = b"invalid json{"
        with self.assertRaises(RuntimeError):
            update_mkvpkg_aur.query_aur(["pkg1"])

    @patch('update_mkvpkg_aur.urllib.request.urlopen')
    def test_query_aur_malformed_response_structure(self, mock_urlopen):
        mock_resp = MagicMock()
        # Test non-dict top level structure (e.g. list)
        mock_resp.read.return_value = json.dumps(["unexpected", "list"]).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        self.assertEqual(update_mkvpkg_aur.query_aur(["pkg1"]), {})

        # Test results containing non-dict elements or missing Name/Version keys
        mock_resp.read.return_value = json.dumps({
            "results": ["not_a_dict", {"Name": "pkg1"}, {"Version": "1.0"}]
        }).encode('utf-8')
        self.assertEqual(update_mkvpkg_aur.query_aur(["pkg1"]), {})

    def test_alpm_vercmp(self):
        # Test basic comparisons and edge cases ported from C rpmvercmp logic
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("1.0", "1.0"), 0)
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("1.0a", "1.0"), -1)
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("1.0.a", "1.0"), 1)
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("1.0", "1.0.0"), -1)
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("2.0-1", "1.0-2"), 1)
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("1:1.0", "2.0"), 1)
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("1.0_a", "1.0_b"), -1)
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("1.0", "1.0_a"), -1)
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("1.0a", "1.0a"), 0)
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("0.99", "1.0"), -1)
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("1.0-1", "1.0-1"), 0)
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("1.0-2", "1.0-1"), 1)
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("1.0.0", "1.0.0"), 0)
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("2.0.1", "2.0"), 1)
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("1.0alpha", "1.0"), -1)
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("1.0beta", "1.0alpha"), 1)
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("1.0rc1", "1.0beta"), 1)
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("1.0.1", "1.0rc1"), 1)
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("1.0+git", "1.0"), 1)
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("1.0-2", "1.0-2"), 0)

    @patch('update_mkvpkg_aur.is_installed')
    @patch('update_mkvpkg_aur.subprocess.run')
    @patch('update_mkvpkg_aur.query_aur')
    @patch('update_mkvpkg_aur.get_mkvpkg_packages_and_versions')
    @patch.object(update_mkvpkg_aur, 'db_path', '/fake/db.tar.gz')
    @patch.object(update_mkvpkg_aur, 'projects_dir', '/fake/projects')
    @patch.object(update_mkvpkg_aur, 'repo_name', 'testrepo')
    @patch('os.path.exists', return_value=True)
    @patch('os.path.isdir', return_value=False)
    @patch('update_mkvpkg_aur.alpm_vercmp')
    def test_main_batched_vercmp(self, mock_alpm_vercmp, mock_isdir, mock_exists, mock_get_pkgs, mock_query_aur, mock_run, mock_is_installed):
        mock_is_installed.return_value = False
        mock_get_pkgs.return_value = {"pkg1": "1.0", "pkg2": "1.0"}
        mock_query_aur.return_value = {"pkg1": "2.0", "pkg2": "1.0-1"}
        mock_is_installed.return_value = False
        # Mock alpm_vercmp output returning 1 for pkg1 (needs update) and 0 for pkg2 (same/older)
        mock_alpm_vercmp.side_effect = lambda a, b: 1 if a == "2.0" else 0
        mock_run.return_value = MagicMock(returncode=0)
        mock_is_installed.return_value = False

        update_mkvpkg_aur.main()

        # Verify alpm_vercmp was called
        mock_alpm_vercmp.assert_any_call("2.0", "1.0")
        mock_alpm_vercmp.assert_any_call("1.0-1", "1.0")
        # Verify repo-remove was called only for pkg1
        mock_run.assert_any_call(["repo-remove", "-w", "--", "/fake/db.tar.gz", "pkg1"], check=True)

    @patch.object(update_mkvpkg_aur, 'db_path', '')
    def test_main_missing_env_vars(self):
        # Should return early
        self.assertIsNone(update_mkvpkg_aur.main())

    @patch.object(update_mkvpkg_aur, 'db_path', '/fake/db.tar.gz')
    @patch.object(update_mkvpkg_aur, 'projects_dir', '/fake/projects')
    @patch.object(update_mkvpkg_aur, 'repo_name', 'testrepo')
    @patch('os.path.exists', return_value=False)
    def test_main_db_not_exists(self, mock_exists):
        # Should return early
        self.assertIsNone(update_mkvpkg_aur.main())

    @patch.object(update_mkvpkg_aur, 'db_path', '/fake/db.tar.gz')
    @patch.object(update_mkvpkg_aur, 'projects_dir', '/fake/projects')
    @patch.object(update_mkvpkg_aur, 'repo_name', 'testrepo')
    @patch('os.path.exists', return_value=True)
    @patch('update_mkvpkg_aur.get_mkvpkg_packages_and_versions')
    def test_main_no_unmodified_pkgs(self, mock_get_pkgs, mock_exists):
        mock_get_pkgs.return_value = {}
        self.assertIsNone(update_mkvpkg_aur.main())

    @patch.object(update_mkvpkg_aur, 'db_path', '/fake/db.tar.gz')
    @patch.object(update_mkvpkg_aur, 'projects_dir', '/fake/projects')
    @patch.object(update_mkvpkg_aur, 'repo_name', 'testrepo')
    @patch('os.path.exists', return_value=True)
    @patch('os.path.isdir', return_value=False)
    @patch('update_mkvpkg_aur.get_mkvpkg_packages_and_versions')
    @patch('update_mkvpkg_aur.query_aur')
    @patch('update_mkvpkg_aur.is_installed')
    @patch('update_mkvpkg_aur.subprocess.run')
    @patch('update_mkvpkg_aur.alpm_vercmp')
    def test_main_priority_check_git(self, mock_alpm_vercmp, mock_run, mock_is_installed, mock_query_aur, mock_get_pkgs, mock_isdir, mock_exists):
        mock_get_pkgs.return_value = {"pkg1": "1.0"}
        mock_query_aur.return_value = {"pkg1": "1.0"} # no update

        # is_installed will return True for "pkg1-git" to trigger priority check
        mock_is_installed.side_effect = lambda pkg: pkg == "pkg1-git"

        update_mkvpkg_aur.main()

        # pkg1 should be removed because pkg1-git is installed
        mock_run.assert_any_call(["repo-remove", "-w", "--", "/fake/db.tar.gz", "pkg1"], check=True)

    @patch.object(update_mkvpkg_aur, 'db_path', '/fake/db.tar.gz')
    @patch.object(update_mkvpkg_aur, 'projects_dir', '/fake/projects')
    @patch.object(update_mkvpkg_aur, 'repo_name', 'testrepo')
    @patch('os.path.exists', return_value=True)
    @patch('os.path.isdir', return_value=False)
    @patch('update_mkvpkg_aur.get_mkvpkg_packages_and_versions')
    @patch('update_mkvpkg_aur.query_aur')
    @patch('update_mkvpkg_aur.is_installed')
    @patch('update_mkvpkg_aur.subprocess.run')
    @patch('update_mkvpkg_aur.alpm_vercmp')
    def test_main_vercmp_valueerror_and_exception(self, mock_alpm_vercmp, mock_run, mock_is_installed, mock_query_aur, mock_get_pkgs, mock_isdir, mock_exists):
        # test Exception in vercmp
        mock_get_pkgs.return_value = {"pkg1": "1.0", "pkg2": "1.0"}
        mock_query_aur.return_value = {"pkg1": "2.0", "pkg2": "2.0"}
        mock_is_installed.return_value = False

        # First call raises Exception, second call returns 1
        mock_alpm_vercmp.side_effect = [Exception("Comparison failed"), 1]

        update_mkvpkg_aur.main()

        # pkg2 will have result=1, so repo-remove called for pkg2
        mock_run.assert_any_call(["repo-remove", "-w", "--", "/fake/db.tar.gz", "pkg2"], check=True)

    @patch('update_mkvpkg_aur.db_path', '/fake/db.tar.gz')
    @patch('update_mkvpkg_aur.projects_dir', '/fake/projects')
    @patch('update_mkvpkg_aur.repo_name', 'testrepo')
    @patch('os.path.exists', return_value=True)
    @patch('os.path.isdir', return_value=False)
    @patch('update_mkvpkg_aur.get_mkvpkg_packages_and_versions')
    @patch('update_mkvpkg_aur.query_aur')
    @patch('update_mkvpkg_aur.is_installed')
    @patch('update_mkvpkg_aur.subprocess.run')
    @patch('update_mkvpkg_aur.alpm_vercmp')
    def test_main_auto_update_installed_true(self, mock_alpm_vercmp, mock_run, mock_is_installed, mock_query_aur, mock_get_pkgs, mock_isdir, mock_exists):
        update_mkvpkg_aur.auto_update_installed = True
        mock_get_pkgs.return_value = {"pkg1": "1.0"}
        mock_query_aur.return_value = {"pkg1": "2.0"}

        mock_is_installed.side_effect = lambda pkg: pkg == "pkg1"

        mock_alpm_vercmp.return_value = 1

        update_mkvpkg_aur.main()

        # pkg1 removed because auto_update_installed is True
        mock_run.assert_any_call(["repo-remove", "-w", "--", "/fake/db.tar.gz", "pkg1"], check=True)
        update_mkvpkg_aur.auto_update_installed = False # Reset

    @patch('update_mkvpkg_aur.db_path', '/fake/db.tar.gz')
    @patch('update_mkvpkg_aur.projects_dir', '/fake/projects')
    @patch('update_mkvpkg_aur.repo_name', 'testrepo')
    @patch('os.path.exists', return_value=True)
    @patch('os.path.isdir', return_value=False)
    @patch('update_mkvpkg_aur.get_mkvpkg_packages_and_versions')
    @patch('update_mkvpkg_aur.query_aur')
    @patch('update_mkvpkg_aur.is_installed')
    @patch('update_mkvpkg_aur.subprocess.run')
    @patch('update_mkvpkg_aur.alpm_vercmp')
    def test_main_auto_update_installed_false(self, mock_alpm_vercmp, mock_run, mock_is_installed, mock_query_aur, mock_get_pkgs, mock_isdir, mock_exists):
        update_mkvpkg_aur.auto_update_installed = False
        mock_get_pkgs.return_value = {"pkg1": "1.0"}
        mock_query_aur.return_value = {"pkg1": "2.0"}

        mock_is_installed.side_effect = lambda pkg: pkg == "pkg1"

        mock_alpm_vercmp.return_value = 1

        update_mkvpkg_aur.main()

        # We need to make sure repo-remove is NOT called
        for call in mock_run.call_args_list:
            self.assertNotEqual(call[0][0][0], "repo-remove")

    @patch.object(update_mkvpkg_aur, 'db_path', '/fake/db.tar.gz')
    @patch.object(update_mkvpkg_aur, 'projects_dir', '/fake/projects')
    @patch.object(update_mkvpkg_aur, 'repo_name', 'testrepo')
    @patch('os.path.exists', return_value=True)
    @patch('os.path.isdir', return_value=False)
    @patch('update_mkvpkg_aur.get_mkvpkg_packages_and_versions')
    @patch('update_mkvpkg_aur.query_aur')
    @patch('update_mkvpkg_aur.is_installed')
    @patch('update_mkvpkg_aur.subprocess.run')
    @patch('update_mkvpkg_aur.alpm_vercmp')
    def test_main_subprocess_exceptions(self, mock_alpm_vercmp, mock_run, mock_is_installed, mock_query_aur, mock_get_pkgs, mock_isdir, mock_exists):
        mock_get_pkgs.return_value = {"pkg1": "1.0"}
        mock_query_aur.return_value = {"pkg1": "2.0"}
        mock_is_installed.return_value = False

        mock_alpm_vercmp.return_value = 1

        def run_side_effect(args, **kwargs):
            if args[0] == "repo-remove":
                raise subprocess.CalledProcessError(1, ["repo-remove"])
            return MagicMock(returncode=0)

        mock_run.side_effect = run_side_effect

        # Should catch exception and print warning, but not crash
        update_mkvpkg_aur.main()

        # Ensure it was called
        mock_run.assert_any_call(["repo-remove", "-w", "--", "/fake/db.tar.gz", "pkg1"], check=True)

    @patch.object(update_mkvpkg_aur, 'db_path', '/fake/db.tar.gz')
    @patch.object(update_mkvpkg_aur, 'projects_dir', '/fake/projects')
    @patch.object(update_mkvpkg_aur, 'repo_name', 'testrepo')
    @patch('os.path.exists', return_value=True)
    @patch('os.path.isdir', return_value=False)
    @patch('update_mkvpkg_aur.get_mkvpkg_packages_and_versions')
    @patch('update_mkvpkg_aur.query_aur')
    @patch('update_mkvpkg_aur.is_installed')
    @patch('update_mkvpkg_aur.subprocess.run')
    @patch('update_mkvpkg_aur.alpm_vercmp')
    def test_main_subprocess_exceptions_sudo(self, mock_alpm_vercmp, mock_run, mock_is_installed, mock_query_aur, mock_get_pkgs, mock_isdir, mock_exists):
        mock_get_pkgs.return_value = {"pkg1": "1.0"}
        mock_query_aur.return_value = {"pkg1": "2.0"}
        mock_is_installed.return_value = False

        mock_alpm_vercmp.return_value = 1

        def run_side_effect(args, **kwargs):
            if args[0] == "sudo":
                raise FileNotFoundError("sudo not found")
            return MagicMock(returncode=0)

        mock_run.side_effect = run_side_effect

        # Should catch exception and print warning, but not crash
        update_mkvpkg_aur.main()

    @patch.object(update_mkvpkg_aur, 'db_path', '/fake/db.tar.gz')
    @patch.object(update_mkvpkg_aur, 'projects_dir', '/fake/projects')
    @patch.object(update_mkvpkg_aur, 'repo_name', 'testrepo')
    @patch('os.path.exists', return_value=True)
    @patch('os.path.isdir', return_value=False)
    @patch('update_mkvpkg_aur.get_mkvpkg_packages_and_versions')
    @patch('update_mkvpkg_aur.query_aur')
    @patch('update_mkvpkg_aur.is_installed')
    @patch('update_mkvpkg_aur.subprocess.run')
    @patch('update_mkvpkg_aur.alpm_vercmp')
    def test_main_continue_when_aur_or_local_missing(self, mock_alpm_vercmp, mock_run, mock_is_installed, mock_query_aur, mock_get_pkgs, mock_isdir, mock_exists):
        # We test lines 139 (continue) where aur_ver or local_ver are None or match
        mock_get_pkgs.return_value = {"pkg1": "1.0", "pkg2": "2.0"}
        mock_query_aur.return_value = {"pkg1": "1.0"} # no update for pkg1
        mock_is_installed.return_value = False

        # We shouldn't even call check_output
        mock_alpm_vercmp.return_value = 0

        update_mkvpkg_aur.main()

        mock_alpm_vercmp.assert_not_called()
        for call in mock_run.call_args_list:
            self.assertNotEqual(call[0][0][0], "repo-remove")


class TestVercmpPurePython(unittest.TestCase):

    def test_parse_evr(self):
        self.assertEqual(update_mkvpkg_aur.parse_evr("1.0"), ("0", "1.0", None))
        self.assertEqual(update_mkvpkg_aur.parse_evr("1.0-1"), ("0", "1.0", "1"))
        self.assertEqual(update_mkvpkg_aur.parse_evr("2:1.0-3"), ("2", "1.0", "3"))
        self.assertEqual(update_mkvpkg_aur.parse_evr("10:2.0.1-0.1"), ("10", "2.0.1", "0.1"))
        self.assertEqual(update_mkvpkg_aur.parse_evr("1.0-alpha-1"), ("0", "1.0-alpha", "1"))

        # Edge cases
        self.assertEqual(update_mkvpkg_aur.parse_evr(""), ("0", "", None))
        self.assertEqual(update_mkvpkg_aur.parse_evr(":"), ("0", "", None))
        self.assertEqual(update_mkvpkg_aur.parse_evr(":1.0"), ("0", "1.0", None))
        self.assertEqual(update_mkvpkg_aur.parse_evr("1:"), ("1", "", None))
        self.assertEqual(update_mkvpkg_aur.parse_evr("1:1.0"), ("1", "1.0", None))
        self.assertEqual(update_mkvpkg_aur.parse_evr("-1"), ("0", "", "1"))
        self.assertEqual(update_mkvpkg_aur.parse_evr("1:1.0-2-3"), ("1", "1.0-2", "3"))
        self.assertEqual(update_mkvpkg_aur.parse_evr("1:1.0-"), ("1", "1.0", ""))
        self.assertEqual(update_mkvpkg_aur.parse_evr("1:-"), ("1", "", ""))
        self.assertEqual(update_mkvpkg_aur.parse_evr("1.0-"), ("0", "1.0", ""))

    def test_alpm_vercmp_edge_cases(self):
        # Equal versions
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("1.0", "1.0"), 0)
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("1.0-1", "1.0-1"), 0)
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("1:1.0", "1:1.0"), 0)

        # Epoch priority
        self.assertGreater(update_mkvpkg_aur.alpm_vercmp("1:1.0", "0:2.0"), 0)
        self.assertLess(update_mkvpkg_aur.alpm_vercmp("1:1.0", "2:0.9"), 0)

        # Release version comparison
        self.assertLess(update_mkvpkg_aur.alpm_vercmp("1.0-1", "1.0-2"), 0)
        self.assertGreater(update_mkvpkg_aur.alpm_vercmp("1.0-10", "1.0-2"), 0)

        # Standard version ordering
        self.assertLess(update_mkvpkg_aur.alpm_vercmp("1.0", "1.0.1"), 0)
        self.assertGreater(update_mkvpkg_aur.alpm_vercmp("1.0.1", "1.0"), 0)
        self.assertLess(update_mkvpkg_aur.alpm_vercmp("1.0.a", "1.0.b"), 0)
        self.assertLess(update_mkvpkg_aur.alpm_vercmp("1.0a", "1.0"), 0)
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("1.01", "1.1"), 0)

        # None / Empty edge cases
        self.assertEqual(update_mkvpkg_aur.alpm_vercmp("", ""), 0)
        self.assertLess(update_mkvpkg_aur.alpm_vercmp("", "1.0"), 0)
        self.assertGreater(update_mkvpkg_aur.alpm_vercmp("1.0", ""), 0)


class TestPkgbuildChecksums(unittest.TestCase):
    def test_pkgbuild_and_srcinfo_checksums(self):
        """Regression test ensuring PKGBUILD and .SRCINFO sha256sums match actual files."""
        import os
        repo_dir = os.path.dirname(os.path.abspath(__file__))
        pkgbuild_path = os.path.join(repo_dir, "PKGBUILD")

        if not os.path.exists(pkgbuild_path):
            self.skipTest("PKGBUILD not found")

        with open(pkgbuild_path, "r", encoding="utf-8") as f:
            pkgbuild_content = f.read()

        import re
        source_match = re.search(r'source=\((.*?)\)', pkgbuild_content, re.DOTALL)
        self.assertIsNotNone(source_match, "source array missing from PKGBUILD")
        sources = [s.strip(' "$\'\t') for s in source_match.group(1).splitlines() if s.strip()]

        sums_match = re.search(r'sha256sums=\((.*?)\)', pkgbuild_content, re.DOTALL)
        self.assertIsNotNone(sums_match, "sha256sums array missing from PKGBUILD")
        declared_sums = [s.strip(' "$\'\t') for s in sums_match.group(1).splitlines() if s.strip()]

        import hashlib
        for src, declared_sum in zip(sources, declared_sums):
            if declared_sum.upper() == 'SKIP':
                continue
            src_path = os.path.join(repo_dir, src)
            self.assertTrue(os.path.exists(src_path), f"Source file {src} referenced in PKGBUILD does not exist")
            with open(src_path, "rb") as f:
                actual_sum = hashlib.sha256(f.read()).hexdigest()
            self.assertEqual(actual_sum, declared_sum, f"SHA256 checksum mismatch for {src}")


if __name__ == '__main__':
    unittest.main()



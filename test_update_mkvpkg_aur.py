import unittest
from unittest.mock import patch, MagicMock
import subprocess
import urllib.request
import json
import update_mkvpkg_aur

class TestUpdateMkvpkgAur(unittest.TestCase):

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
    def test_run_cmd_exception(self, mock_check_output):
        mock_check_output.side_effect = Exception("General error")
        result = update_mkvpkg_aur.run_cmd(["cmd"])
        self.assertEqual(result, "")
        mock_check_output.assert_called_once_with(["cmd"], text=True)

    @patch('update_mkvpkg_aur.subprocess.run')
    def test_is_installed_true(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        self.assertTrue(update_mkvpkg_aur.is_installed("pkg"))
        mock_run.assert_called_once_with(["pacman", "-Qq", "pkg"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @patch('update_mkvpkg_aur.subprocess.run')
    def test_is_installed_false(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        self.assertFalse(update_mkvpkg_aur.is_installed("pkg"))

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
    def test_is_installed_exception(self, mock_run):
        mock_run.side_effect = Exception("System error")
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
        mock_urlopen.side_effect = urllib.error.URLError("Network error")
        with self.assertRaises(RuntimeError):
            update_mkvpkg_aur.query_aur(["pkg1"])

    @patch('update_mkvpkg_aur.is_installed')
    @patch('update_mkvpkg_aur.subprocess.run')
    @patch('update_mkvpkg_aur.subprocess.check_output')
    @patch('update_mkvpkg_aur.query_aur')
    @patch('update_mkvpkg_aur.get_mkvpkg_packages_and_versions')
    @patch.object(update_mkvpkg_aur, 'db_path', '/fake/db.tar.gz')
    @patch.object(update_mkvpkg_aur, 'projects_dir', '/fake/projects')
    @patch.object(update_mkvpkg_aur, 'repo_name', 'testrepo')
    @patch('os.path.exists', return_value=True)
    @patch('os.path.isdir', return_value=False)
    def test_main_batched_vercmp(self, mock_isdir, mock_exists, mock_get_pkgs, mock_query_aur, mock_check_output, mock_run, mock_is_installed):
        mock_is_installed.return_value = False
        mock_get_pkgs.return_value = {"pkg1": "1.0", "pkg2": "1.0"}
        mock_query_aur.return_value = {"pkg1": "2.0", "pkg2": "2.0"}
        mock_is_installed.return_value = False
        # Mock vercmp output returning 1 for pkg1 (needs update) and 0 for pkg2 (same/older)
        mock_check_output.return_value = "1\n0\n"
        mock_run.return_value = MagicMock(returncode=0)
        mock_is_installed.return_value = False

        update_mkvpkg_aur.main()

        # Verify bash script was executed with chunked arguments
        mock_check_output.assert_called_once()
        cmd = mock_check_output.call_args[0][0]
        self.assertEqual(cmd[0:3], ["bash", "-c", 'for ((i=1; i<=$#; i+=2)); do j=$((i+1)); vercmp "${!i}" "${!j}" || echo 0; done'])
        self.assertEqual(cmd[4:], ["2.0", "1.0", "2.0", "1.0"])
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
    @patch('update_mkvpkg_aur.subprocess.check_output')
    def test_main_priority_check_git(self, mock_check_output, mock_run, mock_is_installed, mock_query_aur, mock_get_pkgs, mock_isdir, mock_exists):
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
    @patch('update_mkvpkg_aur.subprocess.check_output')
    def test_main_vercmp_valueerror_and_exception(self, mock_check_output, mock_run, mock_is_installed, mock_query_aur, mock_get_pkgs, mock_isdir, mock_exists):
        # test ValueError in vercmp and Exception in batch
        mock_get_pkgs.return_value = {"pkg1": "1.0", "pkg2": "1.0"}
        mock_query_aur.return_value = {"pkg1": "2.0", "pkg2": "2.0"}
        mock_is_installed.return_value = False

        # First call raises Exception
        mock_check_output.side_effect = Exception("Subprocess failed")

        update_mkvpkg_aur.main()

        # Exception caught, results list extended with 0s.
        # So it shouldn't call repo-remove because all vercmp results are 0
        mock_run.assert_not_called()

        # Let's test ValueError
        mock_check_output.side_effect = None
        mock_check_output.return_value = "invalid_int\n1\n"

        # Reset mock
        mock_run.reset_mock()
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
    @patch('update_mkvpkg_aur.subprocess.check_output')
    def test_main_auto_update_installed_true(self, mock_check_output, mock_run, mock_is_installed, mock_query_aur, mock_get_pkgs, mock_isdir, mock_exists):
        update_mkvpkg_aur.auto_update_installed = True
        mock_get_pkgs.return_value = {"pkg1": "1.0"}
        mock_query_aur.return_value = {"pkg1": "2.0"}

        mock_is_installed.side_effect = lambda pkg: pkg == "pkg1"

        mock_check_output.return_value = "1\n"

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
    @patch('update_mkvpkg_aur.subprocess.check_output')
    def test_main_auto_update_installed_false(self, mock_check_output, mock_run, mock_is_installed, mock_query_aur, mock_get_pkgs, mock_isdir, mock_exists):
        update_mkvpkg_aur.auto_update_installed = False
        mock_get_pkgs.return_value = {"pkg1": "1.0"}
        mock_query_aur.return_value = {"pkg1": "2.0"}

        mock_is_installed.side_effect = lambda pkg: pkg == "pkg1"

        mock_check_output.return_value = "1\n"

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
    @patch('update_mkvpkg_aur.subprocess.check_output')
    def test_main_subprocess_exceptions(self, mock_check_output, mock_run, mock_is_installed, mock_query_aur, mock_get_pkgs, mock_isdir, mock_exists):
        mock_get_pkgs.return_value = {"pkg1": "1.0"}
        mock_query_aur.return_value = {"pkg1": "2.0"}
        mock_is_installed.return_value = False

        mock_check_output.return_value = "1\n"

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
    @patch('update_mkvpkg_aur.subprocess.check_output')
    def test_main_subprocess_exceptions_sudo(self, mock_check_output, mock_run, mock_is_installed, mock_query_aur, mock_get_pkgs, mock_isdir, mock_exists):
        mock_get_pkgs.return_value = {"pkg1": "1.0"}
        mock_query_aur.return_value = {"pkg1": "2.0"}
        mock_is_installed.return_value = False

        mock_check_output.return_value = "1\n"

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
    @patch('update_mkvpkg_aur.subprocess.check_output')
    def test_main_continue_when_aur_or_local_missing(self, mock_check_output, mock_run, mock_is_installed, mock_query_aur, mock_get_pkgs, mock_isdir, mock_exists):
        # We test lines 139 (continue) where aur_ver or local_ver are None or match
        mock_get_pkgs.return_value = {"pkg1": "1.0", "pkg2": "2.0"}
        mock_query_aur.return_value = {"pkg1": "1.0"} # no update for pkg1
        mock_is_installed.return_value = False

        # We shouldn't even call check_output
        mock_check_output.return_value = ""

        update_mkvpkg_aur.main()

        mock_check_output.assert_not_called()
        for call in mock_run.call_args_list:
            self.assertNotEqual(call[0][0][0], "repo-remove")

if __name__ == '__main__':
    unittest.main()

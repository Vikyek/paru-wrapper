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
        mock_urlopen.side_effect = Exception("Network error")
        with self.assertRaises(RuntimeError):
            update_mkvpkg_aur.query_aur(["pkg1"])

    @patch('update_mkvpkg_aur.subprocess.run')
    @patch('update_mkvpkg_aur.subprocess.check_output')
    @patch('update_mkvpkg_aur.query_aur')
    @patch('update_mkvpkg_aur.get_mkvpkg_packages_and_versions')
    @patch.object(update_mkvpkg_aur, 'db_path', '/fake/db.tar.gz')
    @patch.object(update_mkvpkg_aur, 'projects_dir', '/fake/projects')
    @patch.object(update_mkvpkg_aur, 'repo_name', 'testrepo')
    @patch('os.path.exists', return_value=True)
    @patch('os.path.isdir', return_value=False)
    def test_main_batched_vercmp(self, mock_isdir, mock_exists, mock_get_pkgs, mock_query_aur, mock_check_output, mock_run):
        mock_get_pkgs.return_value = {"pkg1": "1.0", "pkg2": "1.0"}
        mock_query_aur.return_value = {"pkg1": "2.0", "pkg2": "2.0"}
        # Mock vercmp output returning 1 for pkg1 (needs update) and 0 for pkg2 (same/older)
        mock_check_output.return_value = "1\n0\n"
        mock_run.return_value = MagicMock(returncode=0)

        update_mkvpkg_aur.main()

        # Verify bash script was executed with chunked arguments
        mock_check_output.assert_called_once()
        cmd = mock_check_output.call_args[0][0]
        self.assertEqual(cmd[0:3], ["bash", "-c", 'for ((i=1; i<=$#; i+=2)); do j=$((i+1)); vercmp "${!i}" "${!j}" || echo 0; done'])
        self.assertEqual(cmd[4:], ["2.0", "1.0", "2.0", "1.0"])
        # Verify repo-remove was called only for pkg1
        mock_run.assert_any_call(["repo-remove", "-w", "--", "/fake/db.tar.gz", "pkg1"], check=True)

    @patch('update_mkvpkg_aur.subprocess.check_output')
    def test_run_cmd_exception(self, mock_check_output):
        mock_check_output.side_effect = Exception("Generic error")
        result = update_mkvpkg_aur.run_cmd(["cmd"])
        self.assertEqual(result, "")

    @patch('update_mkvpkg_aur.subprocess.run')
    def test_is_installed_exception(self, mock_run):
        mock_run.side_effect = Exception("Generic error")
        self.assertFalse(update_mkvpkg_aur.is_installed("pkg"))

    @patch.object(update_mkvpkg_aur, 'db_path', '')
    def test_main_missing_env_vars(self):
        self.assertIsNone(update_mkvpkg_aur.main())

    @patch.object(update_mkvpkg_aur, 'db_path', '/fake/db.tar.gz')
    @patch.object(update_mkvpkg_aur, 'projects_dir', '/fake/projects')
    @patch.object(update_mkvpkg_aur, 'repo_name', 'testrepo')
    @patch('os.path.exists', return_value=False)
    def test_main_db_not_exists(self, mock_exists):
        self.assertIsNone(update_mkvpkg_aur.main())

    @patch('update_mkvpkg_aur.get_mkvpkg_packages_and_versions')
    @patch.object(update_mkvpkg_aur, 'db_path', '/fake/db.tar.gz')
    @patch.object(update_mkvpkg_aur, 'projects_dir', '/fake/projects')
    @patch.object(update_mkvpkg_aur, 'repo_name', 'testrepo')
    @patch('os.path.exists', return_value=True)
    def test_main_no_unmodified_pkgs(self, mock_exists, mock_get_pkgs):
        mock_get_pkgs.return_value = {}
        self.assertIsNone(update_mkvpkg_aur.main())

    @patch('update_mkvpkg_aur.subprocess.run')
    @patch('update_mkvpkg_aur.subprocess.check_output')
    @patch('update_mkvpkg_aur.query_aur')
    @patch('update_mkvpkg_aur.get_mkvpkg_packages_and_versions')
    @patch.object(update_mkvpkg_aur, 'db_path', '/fake/db.tar.gz')
    @patch.object(update_mkvpkg_aur, 'projects_dir', '/fake/projects')
    @patch.object(update_mkvpkg_aur, 'repo_name', 'testrepo')
    @patch('os.path.exists', return_value=True)
    @patch('os.path.isdir', return_value=False)
    def test_main_same_version(self, mock_isdir, mock_exists, mock_get_pkgs, mock_query_aur, mock_check_output, mock_run):
        mock_get_pkgs.return_value = {"pkg1": "1.0"}
        mock_query_aur.return_value = {"pkg1": "1.0"}
        update_mkvpkg_aur.main()
        mock_check_output.assert_not_called()

    @patch('update_mkvpkg_aur.subprocess.run')
    @patch('update_mkvpkg_aur.subprocess.check_output')
    @patch('update_mkvpkg_aur.query_aur')
    @patch('update_mkvpkg_aur.get_mkvpkg_packages_and_versions')
    @patch.object(update_mkvpkg_aur, 'db_path', '/fake/db.tar.gz')
    @patch.object(update_mkvpkg_aur, 'projects_dir', '/fake/projects')
    @patch.object(update_mkvpkg_aur, 'repo_name', 'testrepo')
    @patch('os.path.exists', return_value=True)
    @patch('os.path.isdir', return_value=False)
    def test_main_vercmp_value_error(self, mock_isdir, mock_exists, mock_get_pkgs, mock_query_aur, mock_check_output, mock_run):
        mock_get_pkgs.return_value = {"pkg1": "1.0"}
        mock_query_aur.return_value = {"pkg1": "2.0"}
        mock_check_output.return_value = "invalid_int\n"
        update_mkvpkg_aur.main()
        # Invalid int becomes 0, so no repo-remove called
        mock_run.assert_not_called()

    @patch('update_mkvpkg_aur.subprocess.run')
    @patch('update_mkvpkg_aur.subprocess.check_output')
    @patch('update_mkvpkg_aur.query_aur')
    @patch('update_mkvpkg_aur.get_mkvpkg_packages_and_versions')
    @patch.object(update_mkvpkg_aur, 'db_path', '/fake/db.tar.gz')
    @patch.object(update_mkvpkg_aur, 'projects_dir', '/fake/projects')
    @patch.object(update_mkvpkg_aur, 'repo_name', 'testrepo')
    @patch('os.path.exists', return_value=True)
    @patch('os.path.isdir', return_value=False)
    def test_main_vercmp_exception(self, mock_isdir, mock_exists, mock_get_pkgs, mock_query_aur, mock_check_output, mock_run):
        mock_get_pkgs.return_value = {"pkg1": "1.0"}
        mock_query_aur.return_value = {"pkg1": "2.0"}
        mock_check_output.side_effect = Exception("vercmp error")
        update_mkvpkg_aur.main()
        mock_run.assert_not_called()

    @patch('update_mkvpkg_aur.subprocess.run')
    @patch('update_mkvpkg_aur.subprocess.check_output')
    @patch('update_mkvpkg_aur.query_aur')
    @patch('update_mkvpkg_aur.get_mkvpkg_packages_and_versions')
    @patch('update_mkvpkg_aur.is_installed')
    @patch.object(update_mkvpkg_aur, 'auto_update_installed', False)
    @patch.object(update_mkvpkg_aur, 'db_path', '/fake/db.tar.gz')
    @patch.object(update_mkvpkg_aur, 'projects_dir', '/fake/projects')
    @patch.object(update_mkvpkg_aur, 'repo_name', 'testrepo')
    @patch('os.path.exists', return_value=True)
    @patch('os.path.isdir', return_value=False)
    def test_main_installed_auto_update_disabled(self, mock_isdir, mock_exists, mock_is_installed, mock_get_pkgs, mock_query_aur, mock_check_output, mock_run):
        mock_get_pkgs.return_value = {"pkg1": "1.0"}
        mock_query_aur.return_value = {"pkg1": "2.0"}
        mock_check_output.return_value = "1\n"
        mock_is_installed.return_value = True

        update_mkvpkg_aur.main()
        mock_run.assert_not_called()

    @patch('update_mkvpkg_aur.subprocess.run')
    @patch('update_mkvpkg_aur.subprocess.check_output')
    @patch('update_mkvpkg_aur.query_aur')
    @patch('update_mkvpkg_aur.get_mkvpkg_packages_and_versions')
    @patch('update_mkvpkg_aur.is_installed')
    @patch.object(update_mkvpkg_aur, 'db_path', '/fake/db.tar.gz')
    @patch.object(update_mkvpkg_aur, 'projects_dir', '/fake/projects')
    @patch.object(update_mkvpkg_aur, 'repo_name', 'testrepo')
    @patch('os.path.exists', return_value=True)
    @patch('os.path.isdir', return_value=False)
    def test_main_not_installed(self, mock_isdir, mock_exists, mock_is_installed, mock_get_pkgs, mock_query_aur, mock_check_output, mock_run):
        mock_get_pkgs.return_value = {"pkg1": "1.0"}
        mock_query_aur.return_value = {"pkg1": "2.0"}
        mock_check_output.return_value = "1\n"
        mock_is_installed.return_value = False

        update_mkvpkg_aur.main()
        mock_run.assert_any_call(["repo-remove", "-w", "--", "/fake/db.tar.gz", "pkg1"], check=True)

    @patch('update_mkvpkg_aur.subprocess.run')
    @patch('update_mkvpkg_aur.subprocess.check_output')
    @patch('update_mkvpkg_aur.query_aur')
    @patch('update_mkvpkg_aur.get_mkvpkg_packages_and_versions')
    @patch('update_mkvpkg_aur.is_installed')
    @patch.object(update_mkvpkg_aur, 'db_path', '/fake/db.tar.gz')
    @patch.object(update_mkvpkg_aur, 'projects_dir', '/fake/projects')
    @patch.object(update_mkvpkg_aur, 'repo_name', 'testrepo')
    @patch('os.path.exists', return_value=True)
    @patch('os.path.isdir', return_value=False)
    def test_main_repo_remove_exception(self, mock_isdir, mock_exists, mock_is_installed, mock_get_pkgs, mock_query_aur, mock_check_output, mock_run):
        mock_get_pkgs.return_value = {"pkg1": "1.0"}
        mock_query_aur.return_value = {"pkg1": "2.0"}
        mock_check_output.return_value = "1\n"
        mock_is_installed.return_value = False
        mock_run.side_effect = subprocess.CalledProcessError(1, ["repo-remove"])

        update_mkvpkg_aur.main()
        mock_run.assert_called_once()

    @patch('update_mkvpkg_aur.subprocess.run')
    @patch('update_mkvpkg_aur.subprocess.check_output')
    @patch('update_mkvpkg_aur.query_aur')
    @patch('update_mkvpkg_aur.get_mkvpkg_packages_and_versions')
    @patch('update_mkvpkg_aur.is_installed')
    @patch.object(update_mkvpkg_aur, 'db_path', '/fake/db.tar.gz')
    @patch.object(update_mkvpkg_aur, 'projects_dir', '/fake/projects')
    @patch.object(update_mkvpkg_aur, 'repo_name', 'testrepo')
    @patch('os.path.exists', return_value=True)
    @patch('os.path.isdir', return_value=False)
    def test_main_pacman_sy_exception(self, mock_isdir, mock_exists, mock_is_installed, mock_get_pkgs, mock_query_aur, mock_check_output, mock_run):
        mock_get_pkgs.return_value = {"pkg1": "1.0"}
        mock_query_aur.return_value = {"pkg1": "2.0"}
        mock_check_output.return_value = "1\n"
        mock_is_installed.return_value = False

        def mock_run_side_effect(cmd, *args, **kwargs):
            if cmd == ["sudo", "pacman", "-Sy"]:
                raise subprocess.CalledProcessError(1, cmd)
            return MagicMock(returncode=0)
        mock_run.side_effect = mock_run_side_effect

        update_mkvpkg_aur.main()
        # Expecting 2 calls: repo-remove and pacman -Sy
        self.assertEqual(mock_run.call_count, 2)

if __name__ == '__main__':
    unittest.main()

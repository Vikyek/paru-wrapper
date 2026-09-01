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

    @patch.dict('os.environ', {'PARU_WRAPPER_REPO_DB': '/fake/db.tar.gz', 'PARU_WRAPPER_PROJECTS_DIR': '/fake/projects', 'PARU_WRAPPER_REPO': 'testrepo'})
    def test_main_batched_vercmp(self):
        import importlib
        importlib.reload(update_mkvpkg_aur)

        with patch('update_mkvpkg_aur.subprocess.run') as mock_run, \
             patch('update_mkvpkg_aur.subprocess.check_output') as mock_check_output, \
             patch('update_mkvpkg_aur.query_aur') as mock_query_aur, \
             patch('update_mkvpkg_aur.get_mkvpkg_packages_and_versions') as mock_get_pkgs, \
             patch('update_mkvpkg_aur.is_installed', return_value=False), \
             patch('os.path.exists', return_value=True), \
             patch('os.path.isdir', return_value=False):

            mock_get_pkgs.return_value = {"pkg1": "1.0", "pkg2": "1.0"}
            mock_query_aur.return_value = {"pkg1": "2.0", "pkg2": "1.0"}
            mock_run.return_value = MagicMock(returncode=0)

            update_mkvpkg_aur.main()

            # Verify repo-remove was called only for pkg1 because its version is newer
            mock_run.assert_any_call(["repo-remove", "-w", "--", "/fake/db.tar.gz", "pkg1"], check=True)
            # Check that check_output wasn't called for the version comparison anymore
            mock_check_output.assert_not_called()

if __name__ == '__main__':
    unittest.main()

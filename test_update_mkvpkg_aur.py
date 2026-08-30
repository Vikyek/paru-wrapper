"""
Unit tests for update_mkvpkg_aur.py script
"""
import unittest
from unittest.mock import patch, MagicMock
import subprocess
import urllib.error

# Import the module to be tested
import update_mkvpkg_aur

class TestUpdateMkvpkgAur(unittest.TestCase):
    """
    Test cases for update_mkvpkg_aur functions
    """
    @patch('update_mkvpkg_aur.subprocess.check_output')
    def test_run_cmd_success(self, mock_check_output):
        """Test run_cmd successful execution path."""
        mock_check_output.return_value = " success output \n"
        result = update_mkvpkg_aur.run_cmd(["echo", "success output"])
        self.assertEqual(result, "success output")
        mock_check_output.assert_called_once_with(["echo", "success output"], text=True)

    @patch('update_mkvpkg_aur.subprocess.check_output')
    def test_run_cmd_called_process_error(self, mock_check_output):
        """Test run_cmd behavior on CalledProcessError."""
        mock_check_output.side_effect = subprocess.CalledProcessError(1, ["cmd"])
        result = update_mkvpkg_aur.run_cmd(["cmd"])
        self.assertEqual(result, "")

    @patch('update_mkvpkg_aur.subprocess.check_output')
    def test_run_cmd_general_exception(self, mock_check_output):
        """Test run_cmd behavior on general Exception."""
        mock_check_output.side_effect = Exception("General error")
        result = update_mkvpkg_aur.run_cmd(["cmd"])
        self.assertEqual(result, "")

    @patch('update_mkvpkg_aur.run_cmd')
    @patch('update_mkvpkg_aur.repo_name', 'myrepo')
    def test_get_mkvpkg_packages_and_versions(self, mock_run_cmd):
        mock_run_cmd.return_value = "myrepo pkg1 1.0.0\nmyrepo pkg2 2.0.0\nbadline\n"

        expected = {"pkg1": "1.0.0", "pkg2": "2.0.0"}
        result = update_mkvpkg_aur.get_mkvpkg_packages_and_versions()
        self.assertEqual(result, expected)
        mock_run_cmd.assert_called_once_with(["pacman", "-Sl", "myrepo"])

    @patch('update_mkvpkg_aur.run_cmd')
    @patch('update_mkvpkg_aur.repo_name', '')
    def test_get_mkvpkg_packages_and_versions_no_repo(self, mock_run_cmd):
        result = update_mkvpkg_aur.get_mkvpkg_packages_and_versions()
        self.assertEqual(result, {})
        mock_run_cmd.assert_not_called()

    @patch('update_mkvpkg_aur.urllib.request.urlopen')
    def test_query_aur_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"results": [{"Name": "pkg1", "Version": "1.0.1"}, {"Name": "pkg2", "Version": "2.0.1"}]}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        packages = ["pkg1", "pkg2"]
        result = update_mkvpkg_aur.query_aur(packages)

        self.assertEqual(result, {"pkg1": "1.0.1", "pkg2": "2.0.1"})

        self.assertTrue(mock_urlopen.called)
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.full_url, "https://aur.archlinux.org/rpc/?v=5&type=info&arg[]=pkg1&arg[]=pkg2")

    @patch('update_mkvpkg_aur.urllib.request.urlopen')
    def test_query_aur_exception(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("error")
        packages = ["pkg1"]
        result = update_mkvpkg_aur.query_aur(packages)
        self.assertEqual(result, {})

if __name__ == '__main__':
    unittest.main()

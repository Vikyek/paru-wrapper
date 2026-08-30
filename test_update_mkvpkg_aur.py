"""
Unit tests for update_mkvpkg_aur.py script
"""
import unittest
from unittest.mock import patch
import subprocess
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

if __name__ == '__main__':
    unittest.main()

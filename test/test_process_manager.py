"""
Tests for the ProcessManager class.

This module contains tests for the main functionality of the ProcessManager class.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from mcp_process_manager import ProcessManager  # noqa: E402


class TestProcessManager(unittest.TestCase):
    """Test cases for the ProcessManager class."""

    def setUp(self):
        """Set up test environment."""
        self.manager = ProcessManager()
        self.test_pids = []

    def tearDown(self):
        """Clean up after tests."""
        # Kill and remove all processes
        for pid in self.test_pids:
            self.manager.process_kill(pid)
            self.manager.process_remove(pid)

    def test_process_start(self):
        """Test starting a process."""
        # Start a simple echo process
        status, pid = self.manager.process_start(["echo", "Hello, World!"])

        # Check if process started successfully
        self.assertEqual("success", status)
        self.assertIsNotNone(pid)

        if pid is not None:
            self.test_pids.append(pid)

        # Wait for process to complete
        time.sleep(1)

        # Check process status
        status_info = self.manager.process_status(pid)
        self.assertEqual(["echo", "Hello, World!"], status_info["command"])
        self.assertEqual("completed", status_info["state"])

    def test_process_status(self):
        """Test getting process status."""
        # Start a sleep process
        status, pid = self.manager.process_start(["sleep", "2"])

        # Check if process started successfully
        self.assertEqual("success", status)
        self.assertIsNotNone(pid)

        if pid is not None:
            self.test_pids.append(pid)

        # Check process status while running
        status_info = self.manager.process_status(pid)
        self.assertEqual(["sleep", "2"], status_info["command"])
        self.assertEqual("running", status_info["state"])

        # Wait for process to complete
        time.sleep(3)

        # Check process status after completion
        status_info = self.manager.process_status(pid)
        self.assertEqual("completed", status_info["state"])

    def test_process_kill(self):
        """Test killing a process."""
        # Start a long sleep process
        status, pid = self.manager.process_start(["sleep", "10"])

        # Check if process started successfully
        self.assertEqual("success", status)
        self.assertIsNotNone(pid)

        if pid is not None:
            self.test_pids.append(pid)

        # Kill the process
        kill_status = self.manager.process_kill(pid)
        self.assertEqual("success", kill_status)

        # Wait for process to be killed
        time.sleep(1)

        # Check process status after killing
        status_info = self.manager.process_status(pid)
        self.assertEqual("completed", status_info["state"])

    def test_process_remove(self):
        """Test removing a process from tracking."""
        # Start a process
        status, pid = self.manager.process_start(["echo", "Hello"])

        # Check if process started successfully
        self.assertEqual("success", status)
        self.assertIsNotNone(pid)

        # Wait for process to complete
        time.sleep(1)

        # Remove the process
        remove_status = self.manager.process_remove(pid)
        self.assertEqual("success", remove_status)

        # Check that process is no longer tracked
        status_info = self.manager.process_status(pid)
        self.assertIn("error", status_info["state"])

    def test_process_list(self):
        """Test listing all processes."""
        # Start multiple processes
        status1, pid1 = self.manager.process_start(["sleep", "2"])
        status2, pid2 = self.manager.process_start(["sleep", "3"])

        # Check if processes started successfully
        self.assertEqual("success", status1)
        self.assertEqual("success", status2)

        if pid1 is not None:
            self.test_pids.append(pid1)
        if pid2 is not None:
            self.test_pids.append(pid2)

        # Get process list
        process_list = self.manager.process_list()

        # Check that both processes are in the list
        pids = [p[0] for p in process_list]
        self.assertIn(pid1, pids)
        self.assertIn(pid2, pids)

        # Check process states
        for pid, cmd, state in process_list:
            if pid == pid1 or pid == pid2:
                self.assertEqual("running", state)

    def test_all_kill(self):
        """Test killing all processes."""
        # Start multiple processes
        status1, pid1 = self.manager.process_start(["sleep", "10"])
        status2, pid2 = self.manager.process_start(["sleep", "10"])

        # Check if processes started successfully
        self.assertEqual("success", status1)
        self.assertEqual("success", status2)

        if pid1 is not None:
            self.test_pids.append(pid1)
        if pid2 is not None:
            self.test_pids.append(pid2)

        # Kill all processes
        kill_status = self.manager.all_kill()
        self.assertEqual("success", kill_status)

        # Wait for processes to be killed
        time.sleep(1)

        # Check that all processes are no longer running
        for pid in [pid1, pid2]:
            status_info = self.manager.process_status(pid)
            self.assertEqual("completed", status_info["state"])

    def test_all_remove(self):
        """Test removing all non-running processes."""
        # Start processes
        status1, pid1 = self.manager.process_start(["echo", "Hello"])
        status2, pid2 = self.manager.process_start(["sleep", "5"])

        # Check if processes started successfully
        self.assertEqual("success", status1)
        self.assertEqual("success", status2)

        if pid2 is not None:
            self.test_pids.append(pid2)

        # Wait for first process to complete
        time.sleep(1)

        # Remove all non-running processes
        remove_status = self.manager.all_remove()
        self.assertEqual("success", remove_status)

        # Check that completed process is removed
        status_info1 = self.manager.process_status(pid1)
        self.assertIn("error", status_info1["state"])

        # Check that running process is still tracked
        status_info2 = self.manager.process_status(pid2)
        self.assertEqual("running", status_info2["state"])

    def test_stdio_get_lines(self):
        """Test getting output lines from a process."""
        # Start a process with output
        status, pid = self.manager.process_start(["echo", "Line 1\nLine 2\nLine 3"])

        # Check if process started successfully
        self.assertEqual("success", status)
        self.assertIsNotNone(pid)

        if pid is not None:
            self.test_pids.append(pid)

        # Wait for process to complete
        time.sleep(1)

        # Get output lines
        lines = self.manager.stdio_get_lines(pid)

        # Check output
        self.assertGreaterEqual(len(lines), 1)
        self.assertIn("Line", "".join(lines))

    def test_stdio_send_line(self):
        """Test sending a line to a process."""
        # Use a cat process to echo input
        if os.name == 'nt':  # Windows
            status, pid = self.manager.process_start(["cmd", "/c", "more"])
        else:  # Unix/Linux/Mac
            status, pid = self.manager.process_start(["cat"])

        # Check if process started successfully
        self.assertEqual("success", status)
        self.assertIsNotNone(pid)

        if pid is not None:
            self.test_pids.append(pid)

        # Send a line to the process
        send_status = self.manager.stdio_send_line(pid, "Hello, Process!")
        self.assertEqual("success", send_status)

        # Wait for process to process input
        time.sleep(1)

        # Get output lines
        lines = self.manager.stdio_get_lines(pid)

        # Check that input was echoed
        output = "".join(lines)
        self.assertIn("Hello, Process!", output)

        # Kill the process
        self.manager.process_kill(pid)

    def test_stdio_send_chars(self):
        """Test sending raw characters to a process."""
        # Use a cat process to echo input
        if os.name == 'nt':  # Windows
            status, pid = self.manager.process_start(["cmd", "/c", "more"])
        else:  # Unix/Linux/Mac
            status, pid = self.manager.process_start(["cat"])

        # Check if process started successfully
        self.assertEqual("success", status)
        self.assertIsNotNone(pid)

        if pid is not None:
            self.test_pids.append(pid)

        # Send characters to the process
        send_status = self.manager.stdio_send_chars(pid, "Raw\nChars")
        self.assertEqual("success", send_status)

        # Wait for process to process input
        time.sleep(1)

        # Get output lines
        lines = self.manager.stdio_get_lines(pid)

        # Check that input was echoed
        output = "".join(lines)
        self.assertIn("Raw", output)

        # Kill the process
        self.manager.process_kill(pid)

    def test_search_functionality(self):
        """Test searching process output."""
        # Start a process with searchable output
        cmd: list[str] = ["echo", "Alpha\nBeta\nGamma\nDelta"]
        status, pid = self.manager.process_start(cmd)

        # Check if process started successfully
        self.assertEqual(first="success", second=status)
        self.assertIsNotNone(pid)

        if pid is not None:
            self.test_pids.append(pid)

        # Wait for process to complete
        time.sleep(1)

        # Test string search
        string_matches = self.manager.stdio_search_lines(pid, "string", "eta")
        self.assertEqual(1, len(string_matches))
        self.assertIn("Beta", string_matches[0])

        # Test regex search
        regex_matches = self.manager.stdio_search_lines(pid, "regex", "^[A-Z][a-z]+a$")
        self.assertEqual(4, len(regex_matches))  # All 4 lines match the pattern
        self.assertTrue(any("Alpha" in line for line in regex_matches))
        self.assertTrue(any("Beta" in line for line in regex_matches))
        self.assertTrue(any("Gamma" in line for line in regex_matches))
        self.assertTrue(any("Delta" in line for line in regex_matches))

        # Test wildcard search
        wildcard_matches = self.manager.stdio_search_lines(pid, "wildcard", "*ta")
        self.assertEqual(2, len(wildcard_matches))
        self.assertTrue(any("Beta" in line for line in wildcard_matches))
        self.assertTrue(any("Delta" in line for line in wildcard_matches))

    def test_all_search(self):
        """Test searching across all processes."""
        # Start multiple processes with searchable output
        cmd1 = ["echo", "Process1: Alpha\nProcess1: Beta"]
        cmd2 = ["echo", "Process2: Alpha\nProcess2: Gamma"]

        status1, pid1 = self.manager.process_start(cmd1)
        status2, pid2 = self.manager.process_start(cmd2)

        # Check if processes started successfully
        self.assertEqual("success", status1)
        self.assertEqual("success", status2)

        if pid1 is not None:
            self.test_pids.append(pid1)
        if pid2 is not None:
            self.test_pids.append(pid2)

        # Wait for processes to complete
        time.sleep(1)

        # Search across all processes
        search_results = self.manager.all_search("string", "Alpha")

        # Check search results
        self.assertEqual(2, len(search_results))

        # Verify results contain both processes
        pids = [result[0] for result in search_results]
        self.assertIn(pid1, pids)
        self.assertIn(pid2, pids)

        # Verify each process has the correct output
        for pid, lines in search_results:
            if pid == pid1:
                self.assertTrue(any("Process1: Alpha" in line for line in lines))
            elif pid == pid2:
                self.assertTrue(any("Process2: Alpha" in line for line in lines))


if __name__ == "__main__":
    unittest.main()

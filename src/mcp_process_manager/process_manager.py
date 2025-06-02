"""
Process manager for controlling multiple processes.

This module provides the ProcessManager class which serves as the main interface
for launching, monitoring, and interacting with multiple processes.
"""

import threading
import logging
import os
from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime

from .process_handler import ProcessHandler


class ProcessManager:
    """
    Manages multiple processes and provides a unified interface for process operations.

    This class serves as the main entry point for the MCP Process Manager library,
    providing methods for launching, monitoring, and interacting with processes.

    Example usage:
        manager = ProcessManager()
        status, pid = manager.process_start(["ls", "-la"])
        if "success" in status:
            lines = manager.stdio_get_lines(pid)
    """

    def __init__(self):
        """Initialize a new process manager."""
        self.processes = {}  # pid -> ProcessHandler
        self.lock = threading.RLock()

        # Set up logging
        self._setup_logging()
        self.logger.info("ProcessManager initialized")

    def _setup_logging(self):
        """Set up logging configuration."""
        # Create logs directory if it doesn't exist
        log_dir = "./logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Configure logger
        self.logger = logging.getLogger("mcp_process_manager")
        self.logger.setLevel(logging.INFO)

        # Create file handler with daily rotation
        today = datetime.now().strftime("%Y_%m_%d")
        log_file = f"{log_dir}/mcp_procman_{today}.log"

        # Check if handlers already exist to avoid duplicates
        if not self.logger.handlers:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.INFO)

            # Create formatter
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)

            # Add handler to logger
            self.logger.addHandler(file_handler)

            # Configure log rotation
            try:
                from logging.handlers import RotatingFileHandler
                # Replace the file handler with a rotating one
                self.logger.removeHandler(file_handler)
                rotating_handler = RotatingFileHandler(
                    log_file,
                    maxBytes=10 * 1024 * 1024,  # 10MB
                    backupCount=5
                )
                rotating_handler.setFormatter(formatter)
                self.logger.addHandler(rotating_handler)
            except Exception as e:
                self.logger.error(f"Failed to set up log rotation: {str(e)}")

    def _truncate_for_logging(self, value, max_length=50):
        """Truncate a value for logging purposes."""
        if isinstance(value, str) and len(value) > max_length:
            return value[:max_length - 3] + "..."
        elif isinstance(value, list):
            return [self._truncate_for_logging(item) for item in value[:5]] + (["..."] if len(value) > 5 else [])
        return value

    def process_start(self, command: List[str], timeout: float = 15.0) -> Tuple[str, Optional[int]]:
        """
        Start a new process.

        Args:
            command: Command to execute as a list of strings
            timeout: Maximum time to wait for process to start (seconds)

        Returns:
            Tuple of (status, pid) where status is "success" or "failed: {error}"
            and pid is the process ID or None if failed
        """
        self.logger.info(f"Starting process: command={self._truncate_for_logging(command)}, timeout={timeout}")

        # Validate command
        if not command:
            error_msg = "Command list cannot be empty"
            self.logger.error(error_msg)
            return f"failed: {error_msg}", None

        if not isinstance(command, list):
            error_msg = f"Command must be a list, got {type(command).__name__}"
            self.logger.error(error_msg)
            return f"failed: {error_msg}", None

        try:
            handler = ProcessHandler(command)
            status, pid = handler.start(timeout=timeout)

            if "success" in status and pid is not None:
                with self.lock:
                    self.processes[pid] = handler
                    self.logger.info(f"Process started successfully: pid={pid}")
            else:
                self.logger.error(f"Failed to start process: status={status}")

            return status, pid

        except Exception as e:
            error_msg = f"Unexpected error starting process: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return f"failed: {error_msg}", None

    def process_status(self, pid: int, timeout: float = 15.0) -> Dict[str, Any]:
        """
        Get the status of a process.

        Args:
            pid: Process ID
            timeout: Maximum time to wait for status (seconds)

        Returns:
            Dictionary with process status information
        """
        self.logger.info(f"Getting status for process: pid={pid}, timeout={timeout}")

        with self.lock:
            handler = self.processes.get(pid)
            if not handler:
                self.logger.warning(f"Process not found: pid={pid}")
                return {
                    "command": [],
                    "state": "error: Process not found",
                    "last_five_lines": ""
                }

            status = handler.get_status(timeout=timeout)
            self.logger.info(f"Process status: pid={pid}, state={status['state']}")
            return status

    def process_kill(self, pid: int, timeout: float = 15.0) -> str:
        """
        Kill a process.

        Args:
            pid: Process ID
            timeout: Maximum time to wait for process to terminate (seconds)

        Returns:
            "success" or "failed: {error}"
        """
        self.logger.info(f"Killing process: pid={pid}, timeout={timeout}")

        with self.lock:
            handler = self.processes.get(pid)
            if not handler:
                self.logger.warning(f"Process not found for kill: pid={pid}")
                return "failed: Process not found"

            result = handler.kill(timeout=timeout)
            if "success" in result:
                self.logger.info(f"Process killed successfully: pid={pid}")
            else:
                self.logger.error(f"Failed to kill process: pid={pid}, result={result}")

            return result

    def process_remove(self, pid: int, timeout: float = 15.0) -> str:
        """
        Remove a process from tracking.

        Args:
            pid: Process ID
            timeout: Maximum time to wait (seconds)

        Returns:
            "success" or "failed: {error}"
        """
        self.logger.info(f"Removing process: pid={pid}, timeout={timeout}")

        with self.lock:
            handler = self.processes.get(pid)
            if not handler:
                self.logger.warning(f"Process not found for removal: pid={pid}")
                return "failed: Process not found"

            # Kill process if still running
            if handler.state == "running":
                kill_result = handler.kill(timeout=timeout)
                self.logger.info(f"Kill result during removal: pid={pid}, result={kill_result}")

            # Clean up resources
            try:
                handler.cleanup()
                self.logger.info(f"Process resources cleaned up: pid={pid}")
            except Exception as e:
                self.logger.error(f"Error during cleanup: pid={pid}, error={str(e)}")

            # Remove from tracking
            del self.processes[pid]
            self.logger.info(f"Process removed from tracking: pid={pid}")

            return "success"

    def process_list(self, timeout: float = 15.0) -> List[Tuple[int, List[str], str]]:
        """
        Get a list of all tracked processes.

        Args:
            timeout: Maximum time to wait (seconds)

        Returns:
            List of tuples (pid, command, state)
        """
        self.logger.info(f"Listing all processes: timeout={timeout}")

        result = []

        with self.lock:
            for pid, handler in self.processes.items():
                status = handler.get_status(timeout=timeout)
                result.append((pid, status["command"], status["state"]))

        self.logger.info(f"Process list result: count={len(result)}")
        return result

    def all_kill(self, timeout: float = 15.0) -> str:
        """
        Kill all running processes.

        Args:
            timeout: Maximum time to wait for processes to terminate (seconds)

        Returns:
            "success" or "failed: {error}"
        """
        self.logger.info(f"Killing all running processes: timeout={timeout}")

        errors = []

        with self.lock:
            process_count = len(self.processes)
            running_count = 0

            for pid, handler in list(self.processes.items()):
                if handler.state == "running":
                    running_count += 1
                    result = handler.kill(timeout=timeout)
                    if "failed" in result:
                        errors.append(f"PID {pid}: {result}")
                        self.logger.error(f"Failed to kill process: pid={pid}, error={result}")
                    else:
                        self.logger.info(f"Successfully killed process: pid={pid}")

        self.logger.info(f"All kill operation completed: total={process_count}, running={running_count}, errors={len(errors)}")

        if errors:
            error_msg = f"failed: {'; '.join(errors)}"
            self.logger.error(f"All kill had errors: {error_msg}")
            return error_msg
        return "success"

    def all_remove(self, timeout: float = 15.0) -> str:
        """
        Remove all non-running processes from tracking.

        Args:
            timeout: Maximum time to wait (seconds)

        Returns:
            "success" or "failed: {error}"
        """
        self.logger.info(f"Removing all non-running processes: timeout={timeout}")

        errors = []
        removed_count = 0

        with self.lock:
            for pid, handler in list(self.processes.items()):
                if handler.state != "running":
                    try:
                        # Clean up resources
                        handler.cleanup()

                        # Remove from tracking
                        del self.processes[pid]
                        removed_count += 1
                        self.logger.info(f"Removed non-running process: pid={pid}, state={handler.state}")
                    except Exception as e:
                        error_msg = str(e)
                        errors.append(f"PID {pid}: {error_msg}")
                        self.logger.error(f"Error removing process: pid={pid}, error={error_msg}")

        self.logger.info(f"All remove operation completed: removed={removed_count}, errors={len(errors)}")

        if errors:
            error_msg = f"failed: {'; '.join(errors)}"
            self.logger.error(f"All remove had errors: {error_msg}")
            return error_msg
        return "success"

    def all_search(self,
                   search_type: str,
                   pattern: str,
                   max_lines_per_pid: int = 2,
                   timeout: float = 15.0) -> List[Tuple[int, List[str]]]:
        """
        Search output from all processes.

        Args:
            search_type: Type of search ("string", "regex", or "wildcard")
            pattern: Pattern to search for
            max_lines_per_pid: Maximum number of matching lines per process (default: 2)
            timeout: Maximum time to wait (seconds)

        Returns:
            List of tuples (pid, matching_lines) or error message
        """
        self.logger.info(f"Searching all processes: search_type={search_type}, pattern={self._truncate_for_logging(pattern)}, max_lines_per_pid={max_lines_per_pid}")

        # Validate search_type
        if search_type not in ["string", "regex", "wildcard"]:
            error_msg = f"Invalid search type: {search_type}. Must be 'string', 'regex', or 'wildcard'"
            self.logger.warning(error_msg)
            return [(-1, [f"ERROR: {error_msg}"])]

        # Validate pattern
        if pattern is None or (isinstance(pattern, str) and not pattern):
            error_msg = "Search pattern cannot be empty"
            self.logger.warning(error_msg)
            return [(-1, [f"ERROR: {error_msg}"])]

        result = []
        errors = []

        with self.lock:
            for pid, handler in self.processes.items():
                try:
                    matches = handler.search_output(search_type, pattern, max_lines_per_pid, timeout=timeout)

                    # Check if the search method returned an error
                    if matches and isinstance(matches[0], str) and matches[0].startswith("ERROR:"):
                        errors.append(f"PID {pid}: {matches[0]}")
                        continue

                    if matches:
                        result.append((pid, matches))
                        self.logger.info(f"Found matches in process: pid={pid}, match_count={len(matches)}")
                except Exception as e:
                    error_msg = f"Error searching process {pid}: {str(e)}"
                    self.logger.error(error_msg, exc_info=True)
                    errors.append(f"PID {pid}: {error_msg}")

        if errors:
            self.logger.warning(f"Search completed with errors: {'; '.join(errors)}")
            # Add error information to the result
            result.append((-1, [f"ERROR: {'; '.join(errors)}"]))

        self.logger.info(f"Search completed: processes_with_matches={len(result)}")
        return result

    def stdio_get_lines(self, pid: int, max_lines: int = 5, timeout: float = 15.0) -> List[str]:
        """
        Get recent output lines from a process.

        Args:
            pid: Process ID
            max_lines: Maximum number of lines to return (default: 5)
                      Use 0 to get all lines.
            timeout: Maximum time to wait (seconds)

        Returns:
            List of recent output lines or error message
        """
        self.logger.info(f"Getting output lines: pid={pid}, max_lines={max_lines}, timeout={timeout}")

        with self.lock:
            handler = self.processes.get(pid)
            if not handler:
                error_msg = f"Process not found: pid={pid}"
                self.logger.warning(error_msg)
                return [f"ERROR: {error_msg}"]

            try:
                lines = handler.get_output_lines(max_lines, timeout=timeout)
                self.logger.info(f"Got output lines: pid={pid}, line_count={len(lines)}")
                return lines
            except Exception as e:
                error_msg = f"Error getting output lines: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                return [f"ERROR: {error_msg}"]

    def stdio_search_lines(self,
                          pid: int,
                          search_type: str,
                          pattern: str,
                          max_lines: int = 5,
                          timeout: float = 15.0) -> List[str]:
        """
        Search process output for matching lines.

        Args:
            pid: Process ID
            search_type: Type of search ("string", "regex", or "wildcard")
            pattern: Pattern to search for
            max_lines: Maximum number of matching lines to return (default: 5)
                      Use 0 to get all matching lines.
            timeout: Maximum time to wait (seconds)

        Returns:
            List of matching lines or error message
        """
        self.logger.info(f"Searching process output: pid={pid}, search_type={search_type}, pattern={self._truncate_for_logging(pattern)}, max_lines={max_lines}")

        with self.lock:
            handler = self.processes.get(pid)
            if not handler:
                error_msg = f"Process not found: pid={pid}"
                self.logger.warning(error_msg)
                return [f"ERROR: {error_msg}"]

            # Validate search_type
            if search_type not in ["string", "regex", "wildcard"]:
                error_msg = f"Invalid search type: {search_type}. Must be 'string', 'regex', or 'wildcard'"
                self.logger.warning(error_msg)
                return [f"ERROR: {error_msg}"]

            # Validate pattern
            if pattern is None or (isinstance(pattern, str) and not pattern):
                error_msg = "Search pattern cannot be empty"
                self.logger.warning(error_msg)
                return [f"ERROR: {error_msg}"]

            matches = handler.search_output(search_type, pattern, max_lines, timeout=timeout)

            # Check if the search method returned an error
            if matches and isinstance(matches[0], str) and matches[0].startswith("ERROR:"):
                self.logger.warning(f"Search error: {matches[0]}")
                return matches

            self.logger.info(f"Search results: pid={pid}, match_count={len(matches)}")
            return matches

    def stdio_send_line(self, pid: int, line: str, timeout: float = 15.0) -> str:
        """
        Send a line of text to a process stdin.

        Args:
            pid: Process ID
            line: Line of text to send
            timeout: Maximum time to wait (seconds)

        Returns:
            "success" or "failed: {error}"
        """
        self.logger.info(f"Sending line to process: pid={pid}, line={self._truncate_for_logging(line)}, timeout={timeout}")

        with self.lock:
            handler = self.processes.get(pid)
            if not handler:
                self.logger.warning(f"Process not found for sending line: pid={pid}")
                return "failed: Process not found"

            result = handler.send_line(line, timeout=timeout)
            if "success" in result:
                self.logger.info(f"Line sent successfully: pid={pid}")
            else:
                self.logger.error(f"Failed to send line: pid={pid}, result={result}")

            return result

    def stdio_send_chars(self, pid: int, chars: str, timeout: float = 15.0) -> str:
        """
        Send raw characters to a process stdin.

        Args:
            pid: Process ID
            chars: Characters to send
            timeout: Maximum time to wait (seconds)

        Returns:
            "success" or "failed: {error}"
        """
        self.logger.info(f"Sending chars to process: pid={pid}, chars={self._truncate_for_logging(chars)}, timeout={timeout}")

        with self.lock:
            handler = self.processes.get(pid)
            if not handler:
                self.logger.warning(f"Process not found for sending chars: pid={pid}")
                return "failed: Process not found"

            result = handler.send_chars(chars, timeout=timeout)
            if "success" in result:
                self.logger.info(f"Chars sent successfully: pid={pid}")
            else:
                self.logger.error(f"Failed to send chars: pid={pid}, result={result}")

            return result


def main() -> None:
    """
    Main entry point for the MCP Process Manager when run as a command-line tool.
    This function initializes the ProcessManager and sets up FastMCP integration.
    """
    try:
        from fastmcp import FastMCP
        pm: ProcessManager = ProcessManager()
        mcp: FastMCP = FastMCP()

        pm.logger.info("Adding tools to FastMCP")

        mcp.add_tool(fn=pm.process_list)
        mcp.add_tool(fn=pm.process_start)
        mcp.add_tool(fn=pm.process_status)
        mcp.add_tool(fn=pm.process_kill)
        mcp.add_tool(fn=pm.process_remove)
        mcp.add_tool(fn=pm.stdio_get_lines)
        mcp.add_tool(fn=pm.stdio_search_lines)
        mcp.add_tool(fn=pm.stdio_send_line)
        mcp.add_tool(fn=pm.stdio_send_chars)
        mcp.add_tool(fn=pm.all_kill)
        mcp.add_tool(fn=pm.all_remove)
        mcp.add_tool(fn=pm.all_search)

        # log completed adding tools
        pm.logger.info("All tools added to FastMCP")

        pm.logger.info("Starting FastMCP with stdio transport")
        mcp.run(transport="stdio")
    except ImportError:
        import logging
        logging.basicConfig(level=logging.ERROR)
        logger = logging.getLogger("mcp_process_manager")
        logger.error("FastMCP not found. Please install it to use the MCP Process Manager CLI.")
        print("Error: FastMCP not found. Please install it to use the MCP Process Manager CLI.")
        import sys
        sys.exit(1)
    except Exception as e:
        # clean up process manager
        pm.all_kill()
        pm.all_remove()
        pm.processes.clear()
        import logging
        logging.basicConfig(level=logging.ERROR)
        logger = logging.getLogger("mcp_process_manager")
        logger.error(f"Error in main: {str(e)}", exc_info=True)
        print(f"Error: {str(e)}")
        import sys
        sys.exit(1)
    finally:
        # clean up process manager on weirder edge cases
        pm.all_kill()
        pm.all_remove()
        pm.processes.clear()
        del pm
        del mcp
        exit()


if __name__ == "__main__":
    main()

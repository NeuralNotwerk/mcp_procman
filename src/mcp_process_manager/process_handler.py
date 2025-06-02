"""
Process handler for managing individual processes and their I/O.

This module provides the ProcessHandler class which manages the lifecycle
of a single process, including its I/O operations and buffer management.
"""

import subprocess
import threading
import time
import queue
import logging
from typing import List, Dict, Tuple, Optional, Any
from .ring_buffer import RingBuffer


class ProcessHandler:
    """
    Handles an individual process and its I/O operations.

    This class manages a single process, including launching, monitoring,
    and interacting with the process via stdin/stdout/stderr.

    Example usage:
        handler = ProcessHandler(["ls", "-la"])
        handler.start(timeout=10)
        lines = handler.get_output_lines(5)
    """

    def __init__(self, command: List[str], buffer_size: int = 10 * 1024 * 1024):
        """
        Initialize a new process handler.

        Args:
            command: Command to execute as a list of strings
            buffer_size: Size of the output buffer in bytes (default: 10MB)
        """
        self.command = command
        self.process = None
        self.pid = None
        self.state = "initialized"
        self.error = None
        self.buffer = RingBuffer(max_size_bytes=buffer_size)

        # I/O handling
        self.stdout_thread = None
        self.stderr_thread = None
        self.io_queue = queue.Queue()
        self.stop_event = threading.Event()

        # Lock for thread safety
        self.lock = threading.RLock()

        # Set up logger
        self.logger = logging.getLogger("mcp_process_manager.process_handler")
        self.logger.info(f"ProcessHandler initialized: command={self._truncate_for_logging(command)}")

    def _truncate_for_logging(self, value, max_length=50):
        """Truncate a value for logging purposes."""
        if isinstance(value, str) and len(value) > max_length:
            return value[:max_length - 3] + "..."
        elif isinstance(value, list):
            return [self._truncate_for_logging(item) for item in value[:5]] + (["..."] if len(value) > 5 else [])
        return value

    def start(self, timeout: float = 15.0) -> Tuple[str, Optional[int]]:
        """
        Start the process and begin capturing output.

        Args:
            timeout: Maximum time to wait for process to start (seconds)

        Returns:
            Tuple of (status, pid) where status is "success" or "failed: {error}"
            and pid is the process ID or None if failed
        """
        self.logger.info(f"Starting process: timeout={timeout}")
        try:
            with self.lock:
                if self.process is not None:
                    self.logger.warning("Process already started")
                    return "failed: Process already started", None

                # Validate command
                if not self.command:
                    error_msg = "Command list cannot be empty"
                    self.logger.error(error_msg)
                    return f"failed: {error_msg}", None

                # Start the process
                self.logger.debug(f"Executing command: {self._truncate_for_logging(self.command)}")
                try:
                    self.process = subprocess.Popen(
                        self.command,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        bufsize=0,  # Unbuffered
                        universal_newlines=False  # Binary mode
                    )
                except FileNotFoundError as e:
                    error_msg = f"Command not found: {str(e)}"
                    self.logger.error(error_msg)
                    self.state = "error"
                    self.error = error_msg
                    return f"failed: {error_msg}", None
                except IndexError as e:
                    error_msg = f"Invalid command format: {str(e)}"
                    self.logger.error(error_msg)
                    self.state = "error"
                    self.error = error_msg
                    return f"failed: {error_msg}", None
                except PermissionError as e:
                    error_msg = f"Permission denied: {str(e)}"
                    self.logger.error(error_msg)
                    self.state = "error"
                    self.error = error_msg
                    return f"failed: {error_msg}", None
                except subprocess.SubprocessError as e:
                    error_msg = f"Subprocess error: {str(e)}"
                    self.logger.error(error_msg)
                    self.state = "error"
                    self.error = error_msg
                    return f"failed: {error_msg}", None

                self.pid = self.process.pid
                self.state = "running"
                self.logger.info(f"Process started: pid={self.pid}")

                # Start reader threads
                self.stop_event.clear()
                self.stdout_thread = threading.Thread(
                    target=self._read_output,
                    args=(self.process.stdout, "stdout"),
                    daemon=True
                )
                self.stderr_thread = threading.Thread(
                    target=self._read_output,
                    args=(self.process.stderr, "stderr"),
                    daemon=True
                )

                self.logger.debug("Starting stdout and stderr reader threads")
                self.stdout_thread.start()
                self.stderr_thread.start()

                # Start processor thread
                self.processor_thread = threading.Thread(
                    target=self._process_output,
                    daemon=True
                )
                self.processor_thread.start()
                self.logger.debug("Started output processor thread")

                return "success", self.pid

        except Exception as e:
            self.state = "error"
            self.error = str(e)
            self.logger.error(f"Failed to start process: {str(e)}", exc_info=True)
            return f"failed: {str(e)}", None

    def _read_output(self, pipe: Any, source: str) -> None:
        """
        Read output from the process one byte at a time.

        Args:
            pipe: Pipe to read from (stdout or stderr)
            source: Source identifier ("stdout" or "stderr")
        """
        self.logger.debug(f"Started {source} reader thread")
        try:
            while not self.stop_event.is_set():
                byte = pipe.read(1)
                if not byte:  # End of stream
                    self.logger.debug(f"End of {source} stream")
                    break

                self.io_queue.put((source, byte))
        except Exception as e:
            self.logger.error(f"Error in {source} reader: {str(e)}", exc_info=True)
            self.io_queue.put(("error", str(e)))
        finally:
            self.logger.debug(f"Closing {source} pipe")
            pipe.close()

    def _process_output(self) -> None:
        """Process output bytes from the queue and add to buffer."""
        self.logger.debug("Started output processor thread")
        current_line = bytearray()

        try:
            while not self.stop_event.is_set():
                try:
                    source, data = self.io_queue.get(timeout=0.1)

                    if source == "error":
                        with self.lock:
                            self.error = data
                            self.state = "error"
                            self.logger.error(f"Error in IO processing: {data}")
                        continue

                    # Add byte to current line
                    if isinstance(data, bytes):
                        current_line.extend(data)

                        # If we have a newline, add the complete line to buffer
                        if data == b'\n':
                            with self.lock:
                                line = current_line.decode('utf-8', errors='replace')
                                self.buffer.append(line)
                                self.logger.debug(f"Added complete line to buffer: {self._truncate_for_logging(line)}")
                            current_line = bytearray()

                    self.io_queue.task_done()

                except queue.Empty:
                    # If we have data in current_line, add it to buffer even without newline
                    # This allows detecting prompts that don't end with newline
                    if current_line:
                        with self.lock:
                            line = current_line.decode('utf-8', errors='replace')
                            self.buffer.append(line)
                            self.logger.debug(f"Added partial line to buffer: {self._truncate_for_logging(line)}")
                        current_line = bytearray()

                    # Check if process has terminated
                    with self.lock:
                        if self.process and self.process.poll() is not None:
                            if self.state == "running":
                                exit_code = self.process.poll()
                                if exit_code == 0:
                                    self.state = "completed"
                                    self.logger.info(f"Process completed: pid={self.pid}, exit_code={exit_code}")
                                else:
                                    self.state = f"error: Exit code {exit_code}"
                                    self.logger.warning(f"Process error: pid={self.pid}, exit_code={exit_code}")

                            # Only exit if we've processed all queued output
                            if self.io_queue.empty():
                                self.logger.debug("Output queue empty, processor thread exiting")
                                break
        except Exception as e:
            with self.lock:
                self.error = str(e)
                self.state = "error"
                self.logger.error(f"Error in output processor: {str(e)}", exc_info=True)

    def get_status(self, timeout: float = 15.0) -> Dict[str, Any]:
        """
        Get the current status of the process.

        Args:
            timeout: Maximum time to wait for status (seconds)

        Returns:
            Dictionary with process status information
        """
        self.logger.debug(f"Getting process status: pid={self.pid}, timeout={timeout}")
        with self.lock:
            # Update process state if needed
            if self.process and self.state == "running":
                exit_code = self.process.poll()
                if exit_code is not None:
                    if exit_code == 0:
                        self.state = "completed"
                        self.logger.info(f"Process completed: pid={self.pid}, exit_code={exit_code}")
                    else:
                        self.state = f"error: Exit code {exit_code}"
                        self.logger.warning(f"Process error: pid={self.pid}, exit_code={exit_code}")

            # Get last few lines of output
            last_lines = self.buffer.get_lines(5)
            last_output = "".join(last_lines)
            if len(last_output) > 300:
                last_output = last_output[-300:]

            self.logger.debug(f"Process status: pid={self.pid}, state={self.state}")
            return {
                "command": self.command,
                "state": self.state,
                "last_five_lines": last_output
            }

    def kill(self, timeout: float = 15.0) -> str:
        """
        Kill the process.

        Args:
            timeout: Maximum time to wait for process to terminate (seconds)

        Returns:
            "success" or "failed: {error}"
        """
        self.logger.info(f"Killing process: pid={self.pid}, timeout={timeout}")
        try:
            with self.lock:
                if not self.process:
                    self.logger.warning("No process to kill")
                    return "failed: No process to kill"

                if self.state not in ["running", "error"]:
                    self.logger.warning(f"Process not in killable state: state={self.state}")
                    return "failed: Process not running"

                # Kill the process
                self.logger.debug(f"Sending kill signal to process: pid={self.pid}")
                self.process.kill()

                # Wait for process to terminate
                start_time = time.time()
                while time.time() - start_time < timeout:
                    if self.process.poll() is not None:
                        break
                    time.sleep(0.1)

                # Check if process terminated
                if self.process.poll() is None:
                    self.logger.error(f"Process did not terminate within timeout: pid={self.pid}")
                    return "failed: Process did not terminate within timeout"

                self.state = "completed"
                self.stop_event.set()
                self.logger.info(f"Process killed successfully: pid={self.pid}")

                return "success"

        except Exception as e:
            self.logger.error(f"Error killing process: pid={self.pid}, error={str(e)}", exc_info=True)
            return f"failed: {str(e)}"

    def cleanup(self) -> None:
        """Clean up resources used by the process handler."""
        self.logger.info(f"Cleaning up resources: pid={self.pid}")
        with self.lock:
            if self.process and self.process.poll() is None:
                try:
                    self.logger.debug(f"Killing process during cleanup: pid={self.pid}")
                    self.process.kill()
                except Exception as e:
                    self.logger.error(f"Error killing process during cleanup: pid={self.pid}, error={str(e)}")

            self.stop_event.set()
            self.logger.debug("Stop event set for reader threads")

            # Close pipes if they exist
            if self.process:
                if self.process.stdin:
                    try:
                        self.logger.debug("Closing stdin pipe")
                        self.process.stdin.close()
                    except Exception as e:
                        self.logger.error(f"Error closing stdin: {str(e)}")

    def get_output_lines(self, max_lines: int = 5, timeout: float = 15.0) -> List[str]:
        """
        Get recent output lines from the process.

        Args:
            max_lines: Maximum number of lines to return (default: 5)
                      Use 0 to get all lines.
            timeout: Maximum time to wait (seconds)

        Returns:
            List of recent output lines
        """
        self.logger.debug(f"Getting output lines: pid={self.pid}, max_lines={max_lines}")
        with self.lock:
            lines = self.buffer.get_lines(max_lines)
            self.logger.debug(f"Retrieved {len(lines)} output lines")
            return lines

    def search_output(self,
                      search_type: str,
                      pattern: str,
                      max_lines: int = 5,
                      timeout: float = 15.0) -> List[str]:
        """
        Search process output for matching lines.

        Args:
            search_type: Type of search ("string", "regex", or "wildcard")
            pattern: Pattern to search for
            max_lines: Maximum number of matching lines to return (default: 5)
                      Use 0 to get all matching lines.
            timeout: Maximum time to wait (seconds)

        Returns:
            List of matching lines or error message
        """
        self.logger.debug(f"Searching output: pid={self.pid}, search_type={search_type}, pattern={self._truncate_for_logging(pattern)}, max_lines={max_lines}")
        with self.lock:
            try:
                if search_type == "string":
                    matches = self.buffer.search_string(pattern, max_lines)
                elif search_type == "regex":
                    matches = self.buffer.search_regex(pattern, max_lines)
                elif search_type == "wildcard":
                    matches = self.buffer.search_wildcard(pattern, max_lines)
                else:
                    error_msg = f"Invalid search type: {search_type}. Must be 'string', 'regex', or 'wildcard'"
                    self.logger.warning(error_msg)
                    return [f"ERROR: {error_msg}"]

                # Check if the search method returned an error
                if matches and isinstance(matches[0], str) and matches[0].startswith("ERROR:"):
                    self.logger.warning(f"Search error: {matches[0]}")
                    return matches

                self.logger.debug(f"Search found {len(matches)} matching lines")
                return matches
            except Exception as e:
                error_msg = f"Unexpected error during search: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                return [f"ERROR: {error_msg}"]

    def send_line(self, line: str, timeout: float = 15.0) -> str:
        """
        Send a line of text to the process stdin.

        Args:
            line: Line of text to send
            timeout: Maximum time to wait (seconds)

        Returns:
            "success" or "failed: {error}"
        """
        self.logger.info(f"Sending line to process: pid={self.pid}, line={self._truncate_for_logging(line)}")
        try:
            with self.lock:
                if not self.process:
                    self.logger.warning("No process running")
                    return "failed: No process running"

                if self.state != "running":
                    self.logger.warning(f"Process not in running state: state={self.state}")
                    return "failed: Process not in running state"

                if not self.process.stdin:
                    self.logger.warning("Process stdin not available")
                    return "failed: Process stdin not available"

                # Add newline if not present
                if not line.endswith('\n'):
                    line += '\n'

                # Write to stdin
                self.logger.debug("Writing to process stdin")
                self.process.stdin.write(line.encode('utf-8'))
                self.process.stdin.flush()
                self.logger.debug("Successfully wrote to stdin")

                return "success"

        except Exception as e:
            self.logger.error(f"Error sending line to process: pid={self.pid}, error={str(e)}", exc_info=True)
            return f"failed: {str(e)}"

    def send_chars(self, chars: str, timeout: float = 15.0) -> str:
        """
        Send raw characters to the process stdin.

        Args:
            chars: Characters to send
            timeout: Maximum time to wait (seconds)

        Returns:
            "success" or "failed: {error}"
        """
        self.logger.info(f"Sending chars to process: pid={self.pid}, chars={self._truncate_for_logging(chars)}")
        try:
            with self.lock:
                if not self.process:
                    self.logger.warning("No process running")
                    return "failed: No process running"

                if self.state != "running":
                    self.logger.warning(f"Process not in running state: state={self.state}")
                    return "failed: Process not in running state"

                if not self.process.stdin:
                    self.logger.warning("Process stdin not available")
                    return "failed: Process stdin not available"

                # Write to stdin
                self.logger.debug("Writing raw chars to process stdin")
                self.process.stdin.write(chars.encode('utf-8'))
                self.process.stdin.flush()
                self.logger.debug("Successfully wrote chars to stdin")

                return "success"

        except Exception as e:
            self.logger.error(f"Error sending chars to process: pid={self.pid}, error={str(e)}", exc_info=True)
            return f"failed: {str(e)}"

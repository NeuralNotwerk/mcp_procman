"""
Ring buffer implementation for efficient storage of process output.

This module provides a thread-safe ring buffer with configurable size
that efficiently stores and retrieves process output.
"""

import threading
import re
import fnmatch
import logging
from collections import deque
from typing import List, Union, Pattern


class RingBuffer:
    """
    A thread-safe ring buffer for storing process output with search capabilities.

    The buffer maintains a fixed size and automatically removes oldest entries
    when the buffer is full. It provides methods for adding data, retrieving
    recent lines, and searching through the buffer contents.

    Example usage:
        buffer = RingBuffer(max_size_bytes=1024 * 1024)  # 1MB buffer
        buffer.append("Line 1\n")
        buffer.append("Line 2\n")
        lines = buffer.get_lines(2)  # Get last 2 lines
    """

    def __init__(self, max_size_bytes: int = 10 * 1024 * 1024):
        """
        Initialize a new ring buffer with the specified maximum size.

        Args:
            max_size_bytes: Maximum size of the buffer in bytes (default: 10MB)
        """
        self.max_size_bytes = max_size_bytes
        self.buffer = deque()
        self.current_size = 0
        self.lock = threading.RLock()

        # Set up logger
        self.logger = logging.getLogger("mcp_process_manager.ring_buffer")
        self.logger.info(f"RingBuffer initialized: max_size_bytes={max_size_bytes}")

    def _truncate_for_logging(self, value, max_length=50):
        """Truncate a value for logging purposes."""
        if isinstance(value, str) and len(value) > max_length:
            return value[:max_length - 3] + "..."
        return value

    def append(self, data: str) -> None:
        """
        Add data to the buffer, removing oldest entries if necessary.

        Args:
            data: String data to add to the buffer
        """
        with self.lock:
            data_size = len(data.encode('utf-8'))
            self.logger.debug(f"Appending data: size={data_size} bytes, data={self._truncate_for_logging(data)}")

            # If single entry is larger than buffer, truncate it
            if data_size > self.max_size_bytes:
                self.logger.warning(f"Data size ({data_size} bytes) exceeds buffer size, truncating")
                data = data[-self.max_size_bytes:]
                data_size = self.max_size_bytes

            # Remove oldest entries until we have space
            removed_count = 0
            while self.current_size + data_size > self.max_size_bytes and self.buffer:
                removed = self.buffer.popleft()
                removed_size = len(removed.encode('utf-8'))
                self.current_size -= removed_size
                removed_count += 1

            if removed_count > 0:
                self.logger.debug(f"Removed {removed_count} old entries to make space")

            # Add new data
            self.buffer.append(data)
            self.current_size += data_size
            self.logger.debug(f"Buffer now contains {len(self.buffer)} entries, {self.current_size} bytes")

    def get_lines(self, max_lines: int = 5) -> List[str]:
        """
        Get the most recent lines from the buffer.

        Args:
            max_lines: Maximum number of lines to return (default: 5)
                      Use 0 to get all lines.

        Returns:
            List of the most recent lines
        """
        with self.lock:
            self.logger.debug(f"Getting lines: max_lines={max_lines}, buffer_size={len(self.buffer)}")
            if max_lines <= 0:
                self.logger.debug(f"Returning all {len(self.buffer)} lines")
                return list(self.buffer)

            # Get the last max_lines entries
            result = list(self.buffer)[-max_lines:]
            self.logger.debug(f"Returning {len(result)} lines")
            return result

    def search_string(self, search_str: str, max_lines: int = 5) -> List[str]:
        """
        Search for lines containing the specified string.

        Args:
            search_str: String to search for
            max_lines: Maximum number of matching lines to return (default: 5)
                      Use 0 to get all matching lines.

        Returns:
            List of matching lines or error message
        """
        with self.lock:
            self.logger.debug(f"Searching for string: pattern={self._truncate_for_logging(search_str)}, max_lines={max_lines}")

            if search_str is None:
                error_msg = "Search string cannot be None"
                self.logger.error(error_msg)
                return [f"ERROR: {error_msg}"]

            try:
                matches = [line for line in self.buffer if search_str in line]
                self.logger.debug(f"Found {len(matches)} matches")
            except Exception as e:
                error_msg = f"Error during string search: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                return [f"ERROR: {error_msg}"]

            if max_lines <= 0:
                return matches
            return matches[-max_lines:]

    def search_regex(self, regex_pattern: Union[str, Pattern], max_lines: int = 5) -> List[str]:
        """
        Search for lines matching the specified regex pattern.

        Args:
            regex_pattern: Regular expression pattern to search for
            max_lines: Maximum number of matching lines to return (default: 5)
                      Use 0 to get all matching lines.

        Returns:
            List of matching lines
        """
        with self.lock:
            self.logger.debug(f"Searching with regex: pattern={self._truncate_for_logging(str(regex_pattern))}, max_lines={max_lines}")

            if isinstance(regex_pattern, str):
                try:
                    regex_pattern = re.compile(regex_pattern)
                except re.error as e:
                    error_msg = f"Invalid regex pattern: {str(e)}"
                    self.logger.error(error_msg)
                    # Return a special error indicator that can be detected by the caller
                    return [f"ERROR: {error_msg}"]
                except Exception as e:
                    error_msg = f"Unexpected error compiling regex: {str(e)}"
                    self.logger.error(error_msg, exc_info=True)
                    return [f"ERROR: {error_msg}"]

            try:
                matches = [line for line in self.buffer if regex_pattern.search(line)]
                self.logger.debug(f"Found {len(matches)} regex matches")
            except Exception as e:
                error_msg = f"Error during regex search: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                return [f"ERROR: {error_msg}"]

            if max_lines <= 0:
                return matches
            return matches[-max_lines:]

    def search_wildcard(self, wildcard_pattern: str, max_lines: int = 5) -> List[str]:
        """
        Search for lines matching the specified wildcard pattern.

        Args:
            wildcard_pattern: Wildcard pattern to search for (e.g., "*.txt")
            max_lines: Maximum number of matching lines to return (default: 5)
                      Use 0 to get all matching lines.

        Returns:
            List of matching lines or error message
        """
        with self.lock:
            self.logger.debug(f"Searching with wildcard: pattern={wildcard_pattern}, max_lines={max_lines}")

            if not wildcard_pattern:
                error_msg = "Empty wildcard pattern provided"
                self.logger.error(error_msg)
                return [f"ERROR: {error_msg}"]

            try:
                # Strip whitespace from lines before matching
                matches = [line for line in self.buffer if fnmatch.fnmatch(line.strip(), wildcard_pattern)]
                self.logger.debug(f"Found {len(matches)} wildcard matches")
            except Exception as e:
                error_msg = f"Error in wildcard search: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                return [f"ERROR: {error_msg}"]

            if max_lines <= 0:
                return matches
            return matches[-max_lines:]

    def clear(self) -> None:
        """Clear the buffer contents."""
        with self.lock:
            self.logger.info(f"Clearing buffer: had {len(self.buffer)} entries, {self.current_size} bytes")
            self.buffer.clear()
            self.current_size = 0

    def get_size(self) -> int:
        """
        Get the current size of the buffer in bytes.

        Returns:
            Current buffer size in bytes
        """
        with self.lock:
            self.logger.debug(f"Getting buffer size: {self.current_size} bytes")
            return self.current_size

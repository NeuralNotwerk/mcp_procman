"""
MCP Process Manager - A library for asynchronously launching, monitoring, and controlling external processes.

This package provides tools for managing multiple processes with comprehensive I/O handling capabilities.
"""

import os
import logging
from .process_manager import ProcessManager
from .process_handler import ProcessHandler
from .ring_buffer import RingBuffer

# Set up package-level logging
logger = logging.getLogger("mcp_process_manager")
logger.setLevel(logging.INFO)

# Create logs directory if it doesn't exist
log_dir = "./logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Export public classes
__all__ = ["ProcessManager", "ProcessHandler", "RingBuffer"]

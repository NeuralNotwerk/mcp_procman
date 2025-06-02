# MCP Process Manager

A Python library for asynchronously launching, monitoring, and controlling external processes with comprehensive I/O management capabilities and logging. This allows your tool calling systems and Agents to run commands without the risk of blocking and halting progress waiting for a returned value that may never come.

## Features

- Asynchronous process launching and monitoring
- Combined stdout/stderr capture with configurable ring buffer
- Thread-safe I/O operations with timeout support
- Process interaction via stdin (lines and raw characters)
- Output retrieval and searching capabilities (string, regex, wildcard)
- Non-blocking design to prevent deadlocks
- Comprehensive logging with rotation for diagnostics and debugging

## Installation

```bash
# Clone the repository
git clone git@github.com:NeuralNotwerk/mcp_procman.git

# Install the package
cd mcp_procman
pip install -e .
```

## Project Structure

```
mcp_process_manager/
├── src/
│   └── mcp_process_manager/
│       ├── __init__.py         # Package initialization
│       ├── process_manager.py  # Main ProcessManager class
│       ├── process_handler.py  # Individual process handler
│       └── ring_buffer.py      # Ring buffer implementation
├── test/
│   └── test_process_manager.py # Test suite
├── logs/                       # Log directory (created automatically)
├── setup.py                    # Package setup script
└── README.md                   # This file
```

## Usage

### As a Library

```python
from mcp_process_manager import ProcessManager

# Create a process manager
manager = ProcessManager()

# Start a process
status, pid = manager.process_start(["echo", "Hello, World!"])

# Get process output
lines = manager.stdio_get_lines(pid)
print(lines)

# Start an interactive process
status, pid = manager.process_start(["python", "-c", "while True: print(input('Enter text: '))"])

# Send input to the process
manager.stdio_send_line(pid, "Hello from Python!")

# Get process output
lines = manager.stdio_get_lines(pid)
print(lines)

# Kill the process
manager.process_kill(pid)

# Remove the process from tracking
manager.process_remove(pid)
```

### As a Command-Line Tool

After installation, you can run the MCP Process Manager as a command-line tool:

```bash
# Run the MCP Process Manager
mcp_procman
```

This will start the process manager with FastMCP integration, allowing you to interact with it via the command line.

## Logging

The MCP Process Manager includes comprehensive logging capabilities:

- Logs are stored in the `./logs/` directory (created automatically if it doesn't exist)
- Log files follow the naming pattern `mcp_procman_YYYY_MM_DD.log` with daily rotation
- Log files are limited to 10MB in size with rotation (up to 5 backup files)
- All exceptions, function inputs, and function outputs are logged
- Hierarchical loggers are used for different components:
  - `mcp_process_manager` (root logger)
  - `mcp_process_manager.process_manager`
  - `mcp_process_manager.process_handler`
  - `mcp_process_manager.ring_buffer`

To access logs programmatically:

```python
import logging

# Get the logger
logger = logging.getLogger("mcp_process_manager")

# Set log level if needed
logger.setLevel(logging.DEBUG)  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
```

## API Reference

### Process Management

- `process_start(command, timeout=15.0)`: Start a new process
- `process_status(pid, timeout=15.0)`: Get process status
- `process_kill(pid, timeout=15.0)`: Kill a process
- `process_remove(pid, timeout=15.0)`: Remove a process from tracking
- `process_list(timeout=15.0)`: List all tracked processes
- `all_kill(timeout=15.0)`: Kill all running processes
- `all_remove(timeout=15.0)`: Remove all non-running processes

### I/O Operations

- `stdio_get_lines(pid, max_lines=5, timeout=15.0)`: Get recent output lines
- `stdio_search_lines(pid, search_type, pattern, max_lines=5, timeout=15.0)`: Search process output
- `all_search(search_type, pattern, max_lines_per_pid=2, timeout=15.0)`: Search across all processes
- `stdio_send_line(pid, line, timeout=15.0)`: Send a line to process stdin
- `stdio_send_chars(pid, chars, timeout=15.0)`: Send raw characters to process stdin

## Testing

```bash
# Run tests
python -m unittest discover -s test
```

## License

Apache 2.0

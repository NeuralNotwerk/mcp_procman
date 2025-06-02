# Contributing to MCP Process Manager

Thank you for your interest in contributing to MCP Process Manager! This document provides guidelines and instructions for contributing to this project.

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## How to Contribute

### Reporting Bugs

If you find a bug, please create an issue on GitHub with the following information:

- A clear, descriptive title
- A detailed description of the issue
- Steps to reproduce the bug
- Expected behavior
- Actual behavior
- Screenshots (if applicable)
- Environment information (OS, Python version, etc.)

### Suggesting Enhancements

We welcome suggestions for enhancements! Please create an issue with:

- A clear, descriptive title
- A detailed description of the proposed enhancement
- Any relevant examples or use cases
- Potential implementation approaches (if you have ideas)

### Pull Requests

1. Fork the repository
2. Create a new branch for your feature or bugfix
3. Make your changes
4. Add or update tests as necessary
5. Ensure all tests pass
6. Update documentation as needed
7. Submit a pull request

#### Pull Request Guidelines

- Follow the existing code style and conventions
- Include tests for new functionality
- Update documentation for any changed functionality
- Keep pull requests focused on a single topic
- Reference any related issues in your PR description

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/NeuralNotwerk/mcp_procman.git
   cd mcp_procman
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -e .
   ```

3. Run tests:
   ```bash
   python -m unittest discover -s test
   ```

## Coding Standards

- Follow PEP 8 style guidelines
- Write clear, descriptive docstrings for all functions, classes, and modules
- Include example usage in docstrings for public APIs
- Keep functions and methods focused on a single responsibility
- Use meaningful variable and function names

## License

By contributing to this project, you agree that your contributions will be licensed under the project's [Apache 2.0 License](LICENSE).

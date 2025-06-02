"""
Setup script for the MCP Process Manager package.
"""

from setuptools import setup, find_packages

setup(
    name="mcp_process_manager",
    version="0.1.0",
    description="A library for asynchronously launching, monitoring, and controlling external processes",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="NeuralNotwerk",
    author_email="neuralnotwerk@gmail.com",
    url="https://github.com/NeuralNotwerk/mcp_procman",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.10",
    entry_points={
        'console_scripts': [
            'mcp_procman=mcp_process_manager.process_manager:main',
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Monitoring",
    ],
    project_urls={
        "Bug Tracker": "https://github.com/NeuralNotwerk/mcp_procman/issues",
        "Source Code": "https://github.com/NeuralNotwerk/mcp_procman",
    },
)

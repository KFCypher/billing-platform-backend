#!/usr/bin/env python
"""
Test runner script for the billing platform
"""
import sys
import os
import subprocess

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_tests(args=None):
    """Run pytest with optional arguments."""
    cmd = ['pytest']
    
    if args:
        cmd.extend(args)
    else:
        # Default: run all tests with coverage
        cmd.extend([
            '-v',
            '--cov=.',
            '--cov-report=html',
            '--cov-report=term-missing'
        ])
    
    print(f"Running: {' '.join(cmd)}")
    print("=" * 70)
    
    result = subprocess.run(cmd)
    return result.returncode


if __name__ == '__main__':
    # Pass any command line arguments to pytest
    exit_code = run_tests(sys.argv[1:])
    sys.exit(exit_code)

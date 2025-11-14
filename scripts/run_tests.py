#!/usr/bin/env python3
"""
Test runner script for the RAG system.
Provides convenient commands to run different test suites.
"""
import sys
import subprocess
import argparse


def run_command(cmd):
    """Run a command and return success status."""
    result = subprocess.run(cmd, shell=True)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description='Run RAG system tests')
    parser.add_argument(
        '--type',
        choices=['all', 'unit', 'integration', 'tools', 'stores', 'processors', 'core', 'api'],
        default='all',
        help='Type of tests to run'
    )
    parser.add_argument(
        '--coverage',
        action='store_true',
        help='Run with coverage report'
    )
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--slow',
        action='store_true',
        help='Include slow tests'
    )
    
    args = parser.parse_args()
    
    # Build pytest command
    cmd_parts = ['python', '-m', 'pytest']
    
    if args.verbose:
        cmd_parts.append('-v')
    
    # Add coverage if requested
    if args.coverage:
        cmd_parts.extend(['--cov=src', '--cov-report=html', '--cov-report=term-missing'])
    
    # Select test type
    if args.type == 'unit':
        cmd_parts.extend(['-m', 'unit'])
    elif args.type == 'integration':
        cmd_parts.extend(['-m', 'integration'])
    elif args.type == 'tools':
        cmd_parts.append('tests/test_tools*.py')
    elif args.type == 'stores':
        cmd_parts.append('tests/test_stores.py')
    elif args.type == 'processors':
        cmd_parts.append('tests/test_processors.py')
    elif args.type == 'core':
        cmd_parts.append('tests/test_core_rag.py')
    elif args.type == 'api':
        cmd_parts.append('tests/test_api.py')
    else:
        cmd_parts.append('tests/')
    
    # Exclude slow tests unless requested
    if not args.slow:
        cmd_parts.extend(['-m', 'not slow'])
    
    cmd = ' '.join(cmd_parts)
    print(f"Running: {cmd}\n")
    
    success = run_command(cmd)
    
    if success:
        print("\n✅ All tests passed!")
        if args.coverage:
            print("📊 Coverage report generated in htmlcov/index.html")
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)


if __name__ == '__main__':
    main()


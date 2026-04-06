#!/usr/bin/env python3
"""
WizBot Test Runner - Execute server and monitor WizBot activity.

Run with: python run_test.py
"""

import subprocess
import sys
import time
import threading

def run_server():
    """Run the headless server."""
    try:
        result = subprocess.run([sys.executable, "headless_server.py"], cwd="/d/Python/pyrogue_engine_release")
        return result.returncode
    except Exception as e:
        print(f"Error running server: {e}")
        return 1

def monitor_output(process):
    """Monitor process output in real-time."""
    while True:
        line = process.stdout.readline()
        if not line:
            break
        print(line.decode('utf-8', errors='ignore').rstrip())

if __name__ == "__main__":
    print("="*80)
    print("PYROGUE WIZBOT TEST RUNNER")
    print("="*80)
    print()
    print("Starting headless server with WizBot...")
    print()

    return_code = run_server()
    sys.exit(return_code)

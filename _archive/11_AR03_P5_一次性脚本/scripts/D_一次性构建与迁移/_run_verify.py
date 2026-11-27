#!/usr/bin/env python3
"""Run verify_p0_cleanup.py with the project venv and print output."""
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_PYTHON = os.path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe")
TARGET = os.path.join(PROJECT_ROOT, "scripts", "verify_p0_cleanup.py")

env = os.environ.copy()
env["PYTHONPATH"] = PROJECT_ROOT

print(f"[INFO] venv python: {VENV_PYTHON}")
print(f"[INFO] target: {TARGET}")
print(f"[INFO] PYTHONPATH: {PROJECT_ROOT}")
print("-" * 60)

result = subprocess.run(
    [VENV_PYTHON, TARGET],
    cwd=PROJECT_ROOT,
    env=env,
    check=False,
)
print("-" * 60)
print(f"[EXIT] {result.returncode}")
sys.exit(result.returncode)

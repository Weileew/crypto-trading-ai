#!/usr/bin/env python3
"""Run post-briefing validation/improvement sequence based on skill conventions."""
import os
import subprocess
import sys
from datetime import datetime, timezone

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(SKILL_DIR, "scripts")
REPORTS = os.path.join(SKILL_DIR, "reports")

os.makedirs(REPORTS, exist_ok=True)

COMMANDS = [
    ["python3", os.path.join(SCRIPTS, "signal_validator.py")],
    ["python3", os.path.join(SCRIPTS, "improve.py")],
]

results = []
for cmd in COMMANDS:
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=SCRIPTS)
    results.append({"cmd": " ".join(cmd), "rc": res.returncode, "stdout": res.stdout.strip(), "stderr": res.stderr.strip()})
    print(f"$ {' '.join(cmd)}")
    if res.stdout.strip():
        print(res.stdout.strip())
    if res.returncode != 0 and res.stderr.strip():
        print("[stderr]", res.stderr.strip())
    print("")

# Locate latest files (conservative)
def latest(pattern):
    try:
        files = sorted([os.path.join(REPORTS, f) for f in os.listdir(REPORTS) if f.startswith(pattern) and f.endswith(".json")])
        return files[-1] if files else None
    except Exception:
        return None

perf = latest("signal_performance")
if perf and os.path.exists(perf):
    with open(perf, "r", encoding="utf-8") as f:
        data = f.read(2048)
    print("[validation]", os.path.basename(perf))
    print(data)

print("[done]", datetime.now(timezone.utc).isoformat())

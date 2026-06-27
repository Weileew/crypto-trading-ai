#!/usr/bin/env python3
"""Generate or update reports/health.json heartbeat."""
import json, os, sys
from datetime import datetime, timezone

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEALTH_PATH = os.path.join(SKILL_DIR, "reports", "health.json")
os.makedirs(os.path.dirname(HEALTH_PATH), exist_ok=True)

def main():
    now = datetime.now(timezone.utc).isoformat()
    health = {
        "last_heartbeat": now,
        "generated_by": os.path.basename(__file__),
        "scripts": {},
    }
    # Scan scripts for last-modified times
    scripts_dir = os.path.join(SKILL_DIR, "scripts")
    if os.path.isdir(scripts_dir):
        for fn in os.listdir(scripts_dir):
            if fn.endswith(".py") or fn.endswith(".sh"):
                fpath = os.path.join(scripts_dir, fn)
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath), tz=timezone.utc).isoformat()
                health["scripts"][fn] = {
                    "size": os.path.getsize(fpath),
                    "last_modified": mtime,
                }

    with open(HEALTH_PATH, "w", encoding="utf-8") as f:
        json.dump(health, f, indent=2)
    print(json.dumps(health, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())

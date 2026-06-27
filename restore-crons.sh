#!/bin/bash
# =====================================================
# CRON JOB RESTORE SCRIPT
# Run this on a fresh Hermes installation to recreate
# all trading-advisor + crypto-research cron jobs
# =====================================================
# Generated: 2026-06-27
# Usage: bash restore-crons.sh
# Prerequisites: Hermes Agent installed, skills copied to ~/.hermes/skills/

set -euo pipefail

HERMES_SKILLS="$HOME/.hermes/skills"
TA_DIR="$HERMES_SKILLS/trading-advisor"
CR_DIR="$HERMES_SKILLS/crypto-research"

echo "=== Recreating trading-advisor + crypto-research cron jobs ==="

# Verify skills are in place
for d in "$TA_DIR" "$CR_DIR"; do
  if [[ ! -d "$d" ]]; then
    echo "ERROR: $d not found! Copy skills first."
    exit 1
  fi
done

# --- Cron Job 1: Orchestrator Nightly ---
echo "[1/7] orchestrator-nightly (04:00 daily)"
hermes cron create \\
  --name "orchestrator-nightly" \\
  --schedule "0 4 * * *" \\
  --workdir "$TA_DIR" \\
  --skills trading-advisor \\
  --deliver origin \\
  --prompt "Load trading-advisor skill. From the trading-advisor skill workdir, run the full crypto trading orchestrator pipeline: python3 scripts/orchestrator.py. Wait for completion and report the digest summary."

# --- Cron Job 2: Morning Briefing ---
echo "[2/7] daily-crypto-trading-briefing-morning (08:00)"
hermes cron create \\
  --name "daily-crypto-trading-briefing-morning" \\
  --schedule "0 8 * * *" \\
  --workdir "$TA_DIR" \\
  --skills trading-advisor \\
  --deliver origin \\
  --prompt "Load trading-advisor skill. Run: python3 scripts/briefing.py --compact --save-only --enhanced --orchestrator from workdir $TA_DIR. Wait for the script to finish, then deliver the briefing."

# --- Cron Job 3: Afternoon Briefing ---
echo "[3/7] daily-crypto-trading-briefing-afternoon (14:00)"
hermes cron create \\
  --name "daily-crypto-trading-briefing-afternoon" \\
  --schedule "0 14 * * *" \\
  --workdir "$TA_DIR" \\
  --skills trading-advisor \\
  --deliver origin \\
  --prompt "Load trading-advisor skill. Run: python3 scripts/briefing.py --compact --save-only --enhanced --orchestrator from workdir $TA_DIR. Wait for the script to finish, then deliver the briefing."

# --- Cron Job 4: Paper Trading M2M ---
echo "[4/7] paper-trading-m2m (every 6h)"
hermes cron create \\
  --name "paper-trading-m2m" \\
  --schedule "15 */6 * * *" \\
  --workdir "$TA_DIR" \\
  --skills trading-advisor \\
  --deliver origin \\
  --prompt "Load trading-advisor skill. Run scripts/paper_trader.py --update --summary from workdir $TA_DIR. Wait for the script to output, deliver the mark-to-market summary."

# --- Cron Job 5: Continuous Improvement ---
echo "[5/7] advisor-continuous-improvement (every 12h)"
hermes cron create \\
  --name "advisor-continuous-improvement" \\
  --schedule "0 */12 * * *" \\
  --workdir "$TA_DIR" \\
  --skills trading-advisor \\
  --deliver origin \\
  --prompt "Load trading-advisor skill. Run scripts/improve.py from workdir $TA_DIR. Wait for improvement analysis output."

# --- Cron Job 6: Maintenance ---
echo "[6/7] advisor-maintenance (02:00 daily)"
hermes cron create \\
  --name "advisor-maintenance" \\
  --schedule "0 2 * * *" \\
  --workdir "$TA_DIR" \\
  --skills trading-advisor \\
  --deliver origin \\
  --prompt "Load trading-advisor skill. Run scripts/paper_trader.py --update --summary from workdir $TA_DIR. Run scripts/health_heartbeat.py from workdir $TA_DIR. Deliver combined status."

# --- Cron Job 7: Research Enrichment ---
echo "[7/7] research-playbook-enrichment (05:30 daily)"
hermes cron create \\
  --name "research-playbook-enrichment" \\
  --schedule "30 5 * * *" \\
  --workdir "$CR_DIR" \\
  --skills crypto-research \\
  --deliver origin \\
  --prompt "Enrich crypto research and regenerate the consolidated digest. Execute these steps in order from workdir $CR_DIR: 1) python3 collect_papers_openalex.py --fetch 2) python3 generate_research_digest.py 3) Run query_papers.py to verify. Deliver a brief summary of what was added."

echo ""
echo "=== All cron jobs recreated ==="
echo "Verify with: hermes cron list"

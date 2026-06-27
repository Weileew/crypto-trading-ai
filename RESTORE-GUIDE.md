# Hermes Config Snapshot (secrets redacted)
# Full restore reference — copy this to ~/.hermes/config.yaml on a fresh machine
# Original: 742 lines, saved: key structural sections

## GitHub Auto-Push Setup (for ongoing backup)
# Kept in: ~/.hermes/scripts/auto-push-github.sh
# Cron: auto-push-github (every 15min, deliver=local)
# Relies on: gh authenticated as Weileew
# Token scopes needed: repo, workflow, read:org, admin:public_key
# Repo: https://github.com/Weileew/crypto-trading-ai

## Environment Variables (needed for Hermes to run)
# File: ~/.hermes/.env
# Required:
# - GITHUB_TOKEN=<your-token>  (for auto-push)
# Keys are NOT backed up — paste fresh on new machine

## Hermes Agent Install
# git clone https://github.com/NousResearch/hermes-agent.git
# cd hermes-agent && pip install -e .

## Skills restore
# Copy from this repo to ~/.hermes/skills/
# cp -r trading-advisor ~/.hermes/skills/
# cp -r crypto-research ~/.hermes/skills/

## Cron jobs restore
# bash restore-crons.sh

#!/bin/bash
# Quick refresh: re-copy latest files from Hermes skills into this repo
# Run this whenever you want to snapshot the current state before a big change

set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$HOME/.hermes/skills"

echo "=== Refreshing crypto-trading-ai backup ==="

# --- Trading Advisor ---
echo "-> trading-advisor"
cp "$SKILLS_DIR/trading-advisor/SKILL.md" "$REPO_DIR/trading-advisor/"
cp "$SKILLS_DIR/trading-advisor/scripts/"*.py "$REPO_DIR/trading-advisor/scripts/"
cp "$SKILLS_DIR/trading-advisor/scripts/"*.sh "$REPO_DIR/trading-advisor/scripts/"
cp "$SKILLS_DIR/trading-advisor/references/"*.md "$REPO_DIR/trading-advisor/references/"
cp "$SKILLS_DIR/trading-advisor/strategy/"* "$REPO_DIR/trading-advisor/strategy/"
cp "$SKILLS_DIR/trading-advisor/reports/"*.md "$REPO_DIR/trading-advisor/reports/"
cp "$SKILLS_DIR/trading-advisor/reports/"*.json "$REPO_DIR/trading-advisor/reports/"

# --- Crypto Research ---
echo "-> crypto-research"
cp "$SKILLS_DIR/crypto-research/SKILL.md" "$REPO_DIR/crypto-research/"
find "$SKILLS_DIR/crypto-research/scripts/" -name '*.py' -exec cp {} "$REPO_DIR/crypto-research/" \;
find "$SKILLS_DIR/crypto-research/references/" -name '*.md' -exec cp {} "$REPO_DIR/crypto-research/" \;

# --- Papers (research collection) ---
echo "-> crypto-research/papers"
rm -rf "$REPO_DIR/crypto-research/papers/"
cp -r "$SKILLS_DIR/crypto-research/papers" "$REPO_DIR/crypto-research/papers/"

echo "=== Done. Run 'cd $REPO_DIR && git add -A && git commit -m \"backup refresh\" && git push' ==="

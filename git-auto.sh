#!/bin/bash
# git-auto.sh — Automatic commit & push for Metro Grid Digital Twin
# Usage: bash git-auto.sh [commit-message]
#   If no message is given, a default message with timestamp is used.

set -e

MSG="${1:-"Auto-commit: $(date -u '+%Y-%m-%d %H:%M UTC')"}"
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"

echo "→ Branch: $BRANCH"
echo "→ Message: $MSG"
echo ""

# 1) Stage everything
git add -A

# 2) Check if there's anything to commit
if git diff --cached --quiet 2>/dev/null; then
    echo "✓ Nothing to commit — working tree clean."
    exit 0
fi

# 3) Show summary
echo "Files staged:"
git diff --cached --stat
echo ""

# 4) Commit
git commit -m "$MSG"
echo ""

# 5) Push
echo "→ Pushing to origin/$BRANCH ..."
git push origin "$BRANCH"
echo "✓ Done — pushed successfully."

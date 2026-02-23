#!/usr/bin/env bash
#
# setup.sh — Deploy the Repository Explorer Kit into a target repository.
#
# Usage:
#   ./setup.sh /path/to/cloned/repo
#   ./setup.sh                        # deploys into current directory
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${1:-.}"

# Resolve to absolute path
TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"

echo "┌──────────────────────────────────────────────────┐"
echo "│  Repository Explorer Kit — Setup                 │"
echo "└──────────────────────────────────────────────────┘"
echo ""
echo "Target: $TARGET_DIR"
echo ""

# Check that target is a git repo
if [ ! -d "$TARGET_DIR/.git" ]; then
    echo "ERROR: $TARGET_DIR is not a git repository."
    echo "       Clone a repo first, then run this script."
    exit 1
fi

# Check for Claude Code
if ! command -v claude &> /dev/null; then
    echo "WARNING: Claude Code not found."
    echo "         Install with: npm install -g @anthropic-ai/claude-code"
    echo ""
fi

# Copy files
echo "Copying files..."

cp "$SCRIPT_DIR/CLAUDE.md" "$TARGET_DIR/CLAUDE.md"
echo "  ✓ CLAUDE.md"

cp "$SCRIPT_DIR/PROMPTS.md" "$TARGET_DIR/PROMPTS.md"
echo "  ✓ PROMPTS.md"

cp "$SCRIPT_DIR/repo-explorer-agent.py" "$TARGET_DIR/repo-explorer-agent.py"
chmod +x "$TARGET_DIR/repo-explorer-agent.py"
echo "  ✓ repo-explorer-agent.py"

# Add to .gitignore if it exists
if [ -f "$TARGET_DIR/.gitignore" ]; then
    if ! grep -q ".claude-study/.agent-state" "$TARGET_DIR/.gitignore" 2>/dev/null; then
        echo "" >> "$TARGET_DIR/.gitignore"
        echo "# Repository Explorer Kit — agent state" >> "$TARGET_DIR/.gitignore"
        echo ".claude-study/.agent-state/" >> "$TARGET_DIR/.gitignore"
        echo "  ✓ Updated .gitignore"
    fi
fi

echo ""
echo "Done! You can now run:"
echo ""
echo "  cd $TARGET_DIR"
echo ""
echo "  # Full autonomous analysis"
echo "  python3 repo-explorer-agent.py"
echo ""
echo "  # Quick survey only"
echo "  python3 repo-explorer-agent.py --phases survey --model sonnet"
echo ""
echo "  # Interactive Claude Code session (reads CLAUDE.md automatically)"
echo "  claude"
echo ""

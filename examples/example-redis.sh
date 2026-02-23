#!/usr/bin/env bash
#
# example-redis.sh — Example: Analyze Redis with the Repository Explorer Kit
#
# Prerequisites:
#   - Claude Code installed and authenticated
#   - Git installed
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${1:-$HOME/repo-studies}"

echo "This script will:"
echo "  1. Clone Redis into $WORK_DIR/redis"
echo "  2. Deploy the Repository Explorer Kit"
echo "  3. Run the autonomous agent (survey + nuggets)"
echo ""
read -p "Continue? [y/N] " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# Create workspace
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

# Clone Redis (shallow for speed)
if [ ! -d "redis" ]; then
    echo "Cloning Redis..."
    git clone --depth 100 https://github.com/redis/redis.git
else
    echo "Redis already cloned."
fi

# Deploy kit
echo "Deploying kit..."
bash "$SCRIPT_DIR/setup.sh" "$WORK_DIR/redis"

# Run agent — survey + nuggets (a good first pass)
cd "$WORK_DIR/redis"
echo ""
echo "Starting autonomous analysis..."
echo "  Model: sonnet (fast survey), then opus (deep nuggets)"
echo "  This will take ~30-45 minutes."
echo ""

python3 repo-explorer-agent.py \
    --phases survey broad_nuggets \
    --model sonnet \
    --max-turns 25

echo ""
echo "Survey complete! Results in: $WORK_DIR/redis/.claude-study/"
echo ""
echo "Next steps:"
echo "  # Deep dives with Opus"
echo "  cd $WORK_DIR/redis"
echo "  python3 repo-explorer-agent.py --phases deep_dives decisions --model opus"
echo ""
echo "  # Interactive exploration"
echo "  cd $WORK_DIR/redis"
echo "  claude"

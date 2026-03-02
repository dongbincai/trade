#!/bin/bash
# unlink-workspace.sh - Remove a linked p8 workspace and clean up worktree references
#
# Usage: ./unlink-workspace.sh TARGET_WORKSPACE [SOURCE_WORKSPACE]
#
# Example:
#   ./unlink-workspace.sh ~/work/ponyai4
#   ./unlink-workspace.sh ~/work/ponyai4 ~/work/ponyai
#
# If SOURCE_WORKSPACE is not provided, the script will try to detect it from worktree info.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Find p8 command (handle alias case)
P8_CMD=""
if command -v p8 &> /dev/null; then
    P8_CMD="p8"
elif [ -x "$HOME/.local/bin/pony-repo" ]; then
    P8_CMD="$HOME/.local/bin/pony-repo"
elif command -v pony-repo &> /dev/null; then
    P8_CMD="pony-repo"
else
    log_error "p8 (pony-repo) command not found"
    echo "Please ensure p8 is installed and in PATH, or ~/.local/bin/pony-repo exists"
    exit 1
fi

# Check arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 TARGET_WORKSPACE [SOURCE_WORKSPACE]"
    echo ""
    echo "Arguments:"
    echo "  TARGET_WORKSPACE  Path to linked workspace to remove (e.g., ~/work/ponyai4)"
    echo "  SOURCE_WORKSPACE  Path to source workspace (optional, will auto-detect)"
    echo ""
    echo "Example:"
    echo "  $0 ~/work/ponyai4"
    echo "  $0 ~/work/ponyai4 ~/work/ponyai"
    exit 1
fi

TARGET_WORKSPACE="$1"
SOURCE_WORKSPACE="${2:-}"

# Expand ~ in paths
TARGET_WORKSPACE="${TARGET_WORKSPACE/#\~/$HOME}"
if [ -n "$SOURCE_WORKSPACE" ]; then
    SOURCE_WORKSPACE="${SOURCE_WORKSPACE/#\~/$HOME}"
fi

# Check if target exists
if [ ! -d "$TARGET_WORKSPACE" ]; then
    log_warn "Target workspace does not exist: $TARGET_WORKSPACE"
    log_info "Nothing to delete. If you need to clean up stale worktree references,"
    log_info "run: cd <SOURCE>/.sub-repos && p8 gitall -c worktree prune"
    exit 0
fi

# Try to detect source workspace if not provided
if [ -z "$SOURCE_WORKSPACE" ]; then
    log_info "Detecting source workspace..."
    
    # Check if common repo exists and has worktree info
    if [ -f "$TARGET_WORKSPACE/.sub-repos/common/.git" ]; then
        # .git is a file pointing to the main repo's worktree directory
        # Content looks like: gitdir: /home/user/work/ponyai/.sub-repos/common/.git/worktrees/common
        GITDIR=$(cat "$TARGET_WORKSPACE/.sub-repos/common/.git" | sed 's/gitdir: //')
        # Extract path up to .sub-repos (remove .sub-repos/common/.git/worktrees/...)
        SOURCE_WORKSPACE=$(echo "$GITDIR" | sed 's|/.sub-repos/.*||')
        log_info "Detected source workspace: $SOURCE_WORKSPACE"
    else
        log_error "Cannot detect source workspace. Please provide it as second argument."
        echo "Usage: $0 TARGET_WORKSPACE SOURCE_WORKSPACE"
        exit 1
    fi
fi

# Validate source workspace
if [ ! -d "$SOURCE_WORKSPACE/.sub-repos" ]; then
    log_error "Source workspace does not exist or is invalid: $SOURCE_WORKSPACE"
    exit 1
fi

# Show what will be deleted
log_info "Will delete linked workspace: $TARGET_WORKSPACE"
log_info "Will clean worktree refs in: $SOURCE_WORKSPACE"

# Show current worktree status before deletion
log_info "Current worktree links (before cleanup):"
git -C "$SOURCE_WORKSPACE/.sub-repos/common" worktree list 2>/dev/null | head -5 || true

# Confirm deletion (skip if running non-interactively)
if [ -t 0 ]; then
    echo ""
    read -p "Proceed with deletion? [y/N] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Aborted."
        exit 0
    fi
fi

# Step 1: Remove target workspace
log_info "Removing target workspace..."
rm -rf "$TARGET_WORKSPACE"
log_info "Removed: $TARGET_WORKSPACE"

# Step 2: Clean up worktree references
log_info "Cleaning up worktree references..."
cd "$SOURCE_WORKSPACE/.sub-repos"
$P8_CMD gitall -c worktree prune

# Verify cleanup
log_info "Verifying cleanup..."
REMAINING=$(git -C "$SOURCE_WORKSPACE/.sub-repos/common" worktree list 2>/dev/null | grep -c "$TARGET_WORKSPACE" || true)
if [ "$REMAINING" -eq 0 ]; then
    log_info "Success! Linked workspace removed and worktree references cleaned."
else
    log_warn "Some worktree references may still exist. Run manually:"
    log_warn "  cd $SOURCE_WORKSPACE/.sub-repos && p8 gitall -c worktree prune"
fi

# Show remaining worktrees
log_info "Remaining worktree links:"
git -C "$SOURCE_WORKSPACE/.sub-repos/common" worktree list -v 2>/dev/null || true

#!/bin/bash
# link-workspace.sh - Create a linked p8 workspace using git worktree
#
# Usage: ./link-workspace.sh SOURCE_WORKSPACE TARGET_WORKSPACE [SYMLINKS...]
#
# Example:
#   ./link-workspace.sh ~/work/ponyai2 ~/work/ponyai5
#   ./link-workspace.sh ~/work/ponyai ~/work/ponyai3 "~/SharedVscode/AGENTS.md:AGENTS.md" "~/SharedVscode/.github:.github"
#
# This script:
# 1. Reads repo configuration from source workspace
# 2. Creates target workspace with p8 init
# 3. Replaces cloned repos with git worktree links
# 4. Syncs the new workspace
# 5. Creates optional symlinks

set -e

# Find p8 command (handle alias case)
P8_CMD=""
if command -v p8 &> /dev/null; then
    P8_CMD="p8"
elif [ -x "$HOME/.local/bin/pony-repo" ]; then
    P8_CMD="$HOME/.local/bin/pony-repo"
elif command -v pony-repo &> /dev/null; then
    P8_CMD="pony-repo"
else
    echo "Error: p8 (pony-repo) command not found"
    echo "Please ensure p8 is installed and in PATH, or ~/.local/bin/pony-repo exists"
    exit 1
fi

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

# Check arguments
if [ $# -lt 2 ]; then
    echo "Usage: $0 SOURCE_WORKSPACE TARGET_WORKSPACE [SYMLINKS...]"
    echo ""
    echo "Arguments:"
    echo "  SOURCE_WORKSPACE  Path to existing p8 workspace (e.g., ~/work/ponyai2)"
    echo "  TARGET_WORKSPACE  Path for new linked workspace (e.g., ~/work/ponyai5)"
    echo "  SYMLINKS          Optional symlinks in format 'source:target'"
    echo ""
    echo "Example:"
    echo "  $0 ~/work/ponyai ~/work/ponyai3"
    echo "  $0 ~/work/ponyai2 ~/work/ponyai5 '~/SharedVscode/AGENTS.md:AGENTS.md'"
    exit 1
fi

SOURCE_WORKSPACE=$(realpath "$1")
TARGET_WORKSPACE="$2"
shift 2
SYMLINKS=("$@")

# Validate source workspace
if [ ! -d "$SOURCE_WORKSPACE/.sub-repos" ]; then
    log_error "Source workspace does not exist or is not a valid p8 workspace: $SOURCE_WORKSPACE"
    exit 1
fi

# Check if target already exists
if [ -d "$TARGET_WORKSPACE" ]; then
    log_error "Target workspace already exists: $TARGET_WORKSPACE"
    echo "Please remove it first or choose a different path."
    exit 1
fi

# Get repo configuration from source
log_info "Reading configuration from source workspace..."
cd "$SOURCE_WORKSPACE"
CONFIG_JSON=$($P8_CMD config --show)
REPOS=$(echo "$CONFIG_JSON" | python3 -c "import sys, json; print(','.join(json.load(sys.stdin)['project_list']))")

if [ -z "$REPOS" ]; then
    log_error "Failed to read repo configuration from source workspace"
    exit 1
fi

log_info "Found repos: $REPOS"

# Create target workspace
log_info "Creating target workspace at $TARGET_WORKSPACE..."
mkdir -p "$TARGET_WORKSPACE"
cd "$TARGET_WORKSPACE"

# Initialize with p8
log_info "Initializing workspace with p8..."
$P8_CMD init -g "$REPOS"

# Remove cloned repos
log_info "Removing cloned repos to make room for worktree links..."
cd "$TARGET_WORKSPACE/.sub-repos"
IFS=',' read -ra REPO_ARRAY <<< "$REPOS"
for repo in "${REPO_ARRAY[@]}"; do
    if [ -d "$repo" ]; then
        rm -rf "$repo"
        log_info "  Removed $repo"
    fi
done

# Create worktree links
log_info "Creating worktree links from source workspace..."
for repo in "${REPO_ARRAY[@]}"; do
    SOURCE_REPO="$SOURCE_WORKSPACE/.sub-repos/$repo"
    TARGET_REPO="$TARGET_WORKSPACE/.sub-repos/$repo"
    
    if [ -d "$SOURCE_REPO/.git" ] || [ -f "$SOURCE_REPO/.git" ]; then
        log_info "  Linking $repo..."
        git -C "$SOURCE_REPO" worktree add -d "$TARGET_REPO" 2>&1 || {
            log_error "Failed to create worktree for $repo"
            exit 1
        }
    else
        log_warn "  Skipping $repo (not a git repository)"
    fi
done

# Sync workspace
log_info "Syncing new workspace..."
cd "$TARGET_WORKSPACE/.sub-repos"
$P8_CMD sync

# Create optional symlinks
if [ ${#SYMLINKS[@]} -gt 0 ]; then
    log_info "Creating symlinks..."
    cd "$TARGET_WORKSPACE/.sub-repos"
    for symlink in "${SYMLINKS[@]}"; do
        IFS=':' read -ra PARTS <<< "$symlink"
        SOURCE_PATH="${PARTS[0]}"
        TARGET_NAME="${PARTS[1]}"
        
        # Expand ~ in source path
        SOURCE_PATH="${SOURCE_PATH/#\~/$HOME}"
        
        if [ -e "$SOURCE_PATH" ]; then
            ln -sf "$SOURCE_PATH" "$TARGET_NAME"
            log_info "  Created symlink: $TARGET_NAME -> $SOURCE_PATH"
        else
            log_warn "  Source does not exist, skipping: $SOURCE_PATH"
        fi
    done
fi

# Verify
log_info "Verifying workspace..."
cd "$TARGET_WORKSPACE/.sub-repos"
BRANCH_COUNT=$($P8_CMD branch 2>/dev/null | wc -l)

# Show disk usage comparison
log_info "Disk usage comparison:"
SOURCE_SIZE=$(du -sh "$SOURCE_WORKSPACE" 2>/dev/null | cut -f1)
TARGET_SIZE=$(du -sh "$TARGET_WORKSPACE" 2>/dev/null | cut -f1)
echo "  Source workspace: $SOURCE_SIZE"
echo "  Linked workspace: $TARGET_SIZE"

log_info "Success! Linked workspace created at $TARGET_WORKSPACE"
log_info "Branch list shared: $BRANCH_COUNT branches available"
echo ""
echo "To start working:"
echo "  cd $TARGET_WORKSPACE/.sub-repos"
echo "  p8 start <new_branch_name>"
echo ""
echo "To cleanup later:"
echo "  rm -rf $TARGET_WORKSPACE"
echo "  cd $SOURCE_WORKSPACE/.sub-repos && p8 gitall -c worktree prune"

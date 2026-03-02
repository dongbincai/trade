---
name: linking-p8-workspace
description: Use when creating or deleting a linked p8 workspace that shares branch list with an existing workspace via git worktree, to reduce disk usage while maintaining isolation
---

# Linking P8 Workspace

## Overview

Create or delete a p8 workspace that shares git history with an existing workspace using `git worktree`. The linked workspace shares branch list but can independently checkout different branches.

**Core principle:** Use p8 init first to get proper workspace metadata, then replace repos with worktree links.

**Announce at start:** "I'm using the linking-p8-workspace skill to create/delete a linked workspace."

## When to Use

**Creating:**
- Need a second workspace for parallel development
- Want to reduce disk usage (linked workspace ~3GB vs full clone ~25GB+)
- Need to work on different branches simultaneously across workspaces
- Setting up a workspace for code review while main workspace has uncommitted changes

**Deleting:**
- Removing a linked workspace that's no longer needed
- Cleaning up worktree references

## When NOT to Use

- Need completely independent workspace with separate branch list
- Working with different repo configurations between workspaces
- Source workspace has corrupted git state

## Creating: Use the Script

```bash
# Basic usage
.github/skills/linking-p8-workspace/link-workspace.sh <SOURCE> <TARGET>

# With symlinks
.github/skills/linking-p8-workspace/link-workspace.sh <SOURCE> <TARGET> \
    "~/SharedVscode/AGENTS.md:AGENTS.md" \
    "~/SharedVscode/.github:.github" \
    "~/SharedVscode/docs:docs"
```

## Deleting: Use the Script

```bash
# Basic usage (auto-detects source workspace)
.github/skills/linking-p8-workspace/unlink-workspace.sh <TARGET>

# Or specify source explicitly
.github/skills/linking-p8-workspace/unlink-workspace.sh <TARGET> <SOURCE>
```

**Manual process (if script unavailable):**
```bash
# Step 1: Remove the linked workspace directory
rm -rf <TARGET_WORKSPACE>

# Step 2: Clean up worktree references in source workspace
cd <SOURCE_WORKSPACE>/.sub-repos && p8 gitall -c worktree prune
```

**Verify cleanup:**
```bash
git -C <SOURCE>/.sub-repos/common worktree list -v
# Should only show the source workspace, not the deleted target
```

## Key Checkpoints (Manual Creation)

If creating manually, ensure these critical points:

### ✅ Checkpoint 1: Source workspace must be valid
```bash
cd <SOURCE> && p8 config --show  # Must show project_list
```

### ✅ Checkpoint 2: Must use `p8 init` first
**Why:** Creates `.repo/` metadata that p8 commands need. Direct worktree creation without init will break p8.

### ✅ Checkpoint 3: Repo list must match
Use the **same** repos from source workspace. Different configs = can't share branches.

### ✅ Checkpoint 4: Use `-d` flag for worktree
```bash
git worktree add -d <TARGET_PATH>  # -d = detached HEAD
```
**Why:** p8 manages branch state; detached HEAD lets p8 control it.

### ✅ Checkpoint 5: Must `p8 sync` after linking
Brings worktrees to proper state.

## Common Mistakes

| Mistake | Why it fails |
|---------|--------------|
| Skip `p8 init` | No workspace metadata, p8 commands fail |
| Different repo config | Can't checkout shared branches |
| Forget `p8 sync` | Repos stuck in detached HEAD |
| Only `rm -rf` without `worktree prune` | Stale references block future worktrees |

## Disk Usage

| Type | Size |
|------|------|
| Full clone | 25-45 GB |
| Linked | 3-5 GB |

## Reference

- Official docs: [P8_wiki.md](../publishing-pr-with-p8/P8_wiki.md) "我想链接一个新的 workspace" section
- Create script: [link-workspace.sh](link-workspace.sh)
- Delete script: [unlink-workspace.sh](unlink-workspace.sh)

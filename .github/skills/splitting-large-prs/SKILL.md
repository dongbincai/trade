---
name: splitting-large-prs
description: Use when splitting a large PR/branch into multiple smaller PRs for easier review and incremental merging
---

# Splitting Large PRs

## Overview

When a feature branch has grown too large, split it into smaller, focused PRs that can be reviewed and merged independently.

**Core workflow:**
1. Analyze the source branch to identify logical units
2. Create a split plan document
3. Extract files one PR at a time
4. Handle dependencies between PRs
5. Publish each PR

## Critical Rules

### Copying Files from Source Branch (CRITICAL)
**NEVER use shell redirection** - it triggers VS Code file write confirmation dialogs:
```bash
# ❌ DON'T - requires manual "Allow" clicks
git show branch:path/to/file.cc > path/to/file.cc
```

**Instead, use two-step process:**
1. **Read content** via terminal (outputs to stdout):
   ```bash
   git -C <repo> show <source_branch>:path/to/file.cc
   ```
2. **Write file** using `create_file` tool with the content from step 1.

### Handle Dependencies with Cherry-Pick
When PR-B depends on PR-A's changes:
```bash
# On PR-B branch, cherry-pick PR-A's commit
git -C <repo> cherry-pick <pr_a_branch>
```

### Always Update BUILD Files
After copying source files, check if BUILD needs updates:
```bash
# Compare BUILD definitions
git -C <repo> show <source_branch>:path/to/BUILD | grep -A 50 'name = "target"'
```

Add new targets or dependencies as needed.

### Test Before Commit
```bash
bazel test -c opt --config remote --jobs 8 //path/to:target_test
```

## Split Plan Document

Create a plan in `docs/plans/YYYY-MM-DD-<feature>-pr-split.md`:

```markdown
# Feature PR Split Plan

**Goal:** Split <source_branch> into N smaller PRs

## Phase 1: Independent PRs (no dependencies)
### PR1: [Module] Description
**Branch:** `pr1_branch_name`
**Files:**
- path/to/file1.cc
- path/to/file1.h
**Commit Message:**
[Module] One-line summary

## Phase 2: Dependent PRs (stack)
### PR2: [Module] Description
**Branch:** `pr2_branch_name`
**Base:** stack on PR1
...

## Dependency Graph
PR1 ──┐
PR2 ──┼──→ PR5
PR3 ──┘
```

## Workflow

### Step 1: Create New Branch
```bash
p8 start <pr_branch_name>
```

### Step 2: Extract Files
For each file:
```bash
# Read content
git -C <repo> show <source_branch>:path/to/file.cc
# Then use create_file tool to write
```

### Step 3: Update BUILD
Add new cc_library/cc_test targets with correct deps.

### Step 4: Test
```bash
bazel test -c opt --config remote --jobs 8 //path/to:target_test
```

### Step 5: Commit
```bash
p8 stage -A
cd <repo> && git commit -m "[Module] Description

详细说明"
```

### Step 6: Publish
```bash
p8 publish --no-unit-test --no-iwyu --create-pr --pr-title "[Module] Description"
```

## Handling Pre-Publish Failures

### IWYU Failures
Use `--no-iwyu` flag to skip IWYU checks (recommended for split PRs).

### sort_include / auto_deps Changes
These tools auto-fix files. After pre-publish modifies files:
```bash
p8 status  # See what changed
cd <repo> && git add -A && git commit --amend --no-edit
p8 publish --no-unit-test --no-iwyu  # Retry
```

### Fixes Need to Go to Different Commit (Stack)
If you have a stack (PR-A → PR-B) and pre-publish fixes belong to PR-A:
```bash
# Stash the fixes
git -C <repo> stash

# Interactive rebase to edit PR-A's commit
GIT_SEQUENCE_EDITOR="sed -i 's/pick <pr_a_hash>/edit <pr_a_hash>/'" git -C <repo> rebase -i <base_hash>

# Apply fixes to PR-A
git -C <repo> stash pop
git -C <repo> add -A && git -C <repo> commit --amend --no-edit

# Continue rebase
git -C <repo> rebase --continue
```

## Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| `git show > file` asks for permission | Use `git show` + `create_file` tool |
| Missing dependency in new branch | Cherry-pick the dependency commit |
| BUILD file not updated | Compare with source branch's BUILD |
| IWYU keeps failing | Add `--no-iwyu` flag |
| Pre-publish changes wrong commit in stack | Use `git rebase -i` to amend correct commit |
| Forgot to test before publish | Always `bazel test` first |

## Example: Extracting a Single PR

```bash
# 1. Start branch
p8 start lio_se3_spline

# 2. Read file content (terminal outputs it)
git -C map show lio_add_local_mapping:localization/lidar_inertial_odometry/local_mapper/se3_spline.h
# → Use create_file tool with this content

git -C map show lio_add_local_mapping:localization/lidar_inertial_odometry/local_mapper/se3_spline.cc
# → Use create_file tool with this content

# 3. Check BUILD and update
git -C map show lio_add_local_mapping:localization/lidar_inertial_odometry/local_mapper/BUILD | grep -A 30 'name = "se3_spline"'
# → Update BUILD with replace_string_in_file tool

# 4. Test
bazel test -c opt --config remote --jobs 8 //map/localization/lidar_inertial_odometry/local_mapper:se3_spline_test

# 5. Commit
p8 stage -A
cd map && git commit -m "[LIO] Add SE3 spline for continuous trajectory

添加基于B-spline的SE3连续轨迹表示"

# 6. Publish
p8 publish --no-unit-test --no-iwyu --create-pr --pr-title "[LIO] Add SE3 spline for continuous trajectory"
```

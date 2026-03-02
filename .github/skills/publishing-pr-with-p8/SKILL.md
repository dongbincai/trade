---
name: publishing-pr-with-p8
description: Use when publishing code changes, creating PRs, starting new branches, or managing multi-repo workflows in this codebase - p8 is the multi-repo tool replacing standard git commands
---

# Publishing PR with P8

## Overview

P8 (pony-repo) manages multiple git repositories as a unified workspace. Use `p8` instead of `git` for branch operations, publishing, and PR management.

**Core principle:** Always check `p8 status` first, run clang-tidy before publishing, handle IWYU/format issues iteratively.

## Critical Notes

### P8 vs Git Command Split (MANDATORY)
**Branch operations (no commit message) → Use `p8`:**
- `p8 start <branch>` - create branch
- `p8 checkout <branch>` - switch branch
- `p8 status` - check status
- `p8 stage -A` - stage all changes
- `p8 stash` / `p8 stash --pop` - stash operations
- `p8 sync` - sync with upstream
- `p8 publish` - publish PR

**Commit message operations → Use `git` in each repo:**
- `cd <repo> && git commit -m "msg"` - initial commit
- `cd <repo> && git commit --amend -m "msg"` - amend with new message
- `cd <repo> && git commit --amend --no-edit` - amend without changing message

**NEVER use `p8 commit --amend`** - it opens interactive editor.

### Avoid Interactive Commands
Agent cannot interact with vim/nano. Use non-interactive alternatives:

| ❌ DON'T USE | ✅ USE INSTEAD |
|-------------|----------------|
| `p8 diff` | `p8 diff ... \| head -500` |
| `p8 commit --amend` | `cd <repo> && git commit --amend -m "msg"` |
| `git commit --amend` (no -m) | `git commit --amend --no-edit` or `-m "msg"` |

### Long-Running Commands
`p8 publish` takes 1-5 minutes. Stages:
1. "Extracting to /tmp/..." - NORMAL, wait!
2. "Executing task ..." - Running checks
3. "Start git push branch ..." - Pushing
4. Creating PR on GitHub

**NEVER interrupt a running `p8 publish` command.**

### Understanding "Set xxx to failure/success" Output
```
Set localization-regression to failure in github
Set clang-tidy to failure in github
```
**This is NOT a failure-la /home/zubingtan/work/ponyai3/.sub-repos/.github/* It means:
- `success` = CI check NOT needed, skip it
- `failure` = CI check WILL RUN, initial status pending

### Auto-Retry When PR Missing
If output shows "project X doesn't have a pull request", retry with:
```bash
p8 publish --no-unit-test --no-iwyu --create-pr --pr-title="[MODULE] Title"
```

## Quick Reference

| Task | Command |
|------|---------|
| Check status | `p8 status` |
| Stage all | `p8 stage -A` |
| Run clang-tidy | `bazel run //:clang_tidy` |
| Amend commit | `cd <repo> && git commit --amend --no-edit` |
| First-time PR | `p8 publish --no-unit-test --no-iwyu --create-pr --pr-title="[MODULE] Title"` |
| Update PR | `p8 publish --no-unit-test --no-iwyu` |
| Start branch | `p8 start <branch_name>` |
| Stash/Pop | `p8 stash -m <msg>` / `p8 stash --pop` |
| View diff | `p8 diff --target-commit=MERGE_BASE \| head -500` |
| Sync upstream | `p8 sync` or `p8 sync --latest` |

## Other Important References

If some problems you can not solve, please refer to the following reference documents:

- [how to use P8](P8_wiki.md)
- [how to use P8 stack](P8_stack_wiki.md)

## Publishing a PR

### Step 1: Check Status
```bash
p8 status
```
Note which repos have changes (e.g., `common`, `map`).

### Step 2: Run clang-tidy
```bash
bazel run //:clang_tidy 2>&1 | grep -E "(ERROR|error:|Build did NOT complete|Build completed successfully)"
```

Common issues:
- **missing_field_init_value**: Initialize pointer members to `nullptr`
- **rule-of-five**: Add `= delete` for copy/move constructors
- **No type alias in header globally**: Move `using` inside namespaces

Fix errors, then: `p8 stage -A && cd <repo> && git commit --amend --no-edit`

### Step 3: Request Code Review
After clang-tidy passes, request a code review using the `requesting-code-review` skill:

1. View changed files and diff:
```bash
# List all changed files across repos
p8 diff --target-commit=MERGE_BASE --name-status
```

For detailed diff, use VS Code's `get_changed_files` tool (preferred) or Source Control view, which provides structured diff output without terminal truncation issues.

2. Dispatch `superpowers:code-reviewer` subagent with:
   - `{WHAT_WAS_IMPLEMENTED}` - Summary of your changes
   - `{PLAN_OR_REQUIREMENTS}` - Original requirements or task description
   - `{CHANGED_FILES}` - Output from `--name-status` above
   - `{DESCRIPTION}` - Brief summary

3. Address feedback:
   - **Critical/Important issues**: Fix before publishing
   - **Minor issues**: Can be addressed in follow-up

**Note:** For C++/Protobuf changes, the review MUST include checks from `cpp-coding-in-this-codebase` skill.

### Step 4: Stage Changes
```bash
p8 stage -A
```

### Step 5: Regenerate Commit Message
View diff and generate NEW message based on current changes:
```bash
p8 diff --target-commit=MERGE_BASE | head -500
```

For EACH changed repo:
```bash
cd /path/to/.sub-repos/<repo> && git commit --amend -m "[MODULE] English summary

中文详细说明：
* 要点一
* 要点二"
```

### Step 6: Publish
```bash
# First-time (no PR exists):
p8 publish --no-unit-test --no-iwyu --create-pr --pr-title="[MODULE] Title"

# Update existing PR:
p8 publish --no-unit-test --no-iwyu
```

### Step 7: Handle Pre-Publish Failures (Iterative)
If publish fails, handle based on failure type:

**auto_deps_check failure:**
p8 publish already auto-fixed the BUILD file. Just commit the fix:
```bash
cd <repo> && git add -A && git commit --amend --no-edit
```

**cpp_lint failure (line length, formatting):**
Use clang-format to fix - NEVER manually edit:
```bash
clang-format-13 -i path/to/file.cc path/to/file.h
cd <repo> && git add -A && git commit --amend --no-edit
```

**sort_include failure:**
```bash
mpm install sort_include && sort_include path/to/file.h
cd <repo> && git add -A && git commit --amend --no-edit
```

**IWYU/unclean files:**
1. Check: `p8 status`
2. Trust automated fixes (IWYU, BUILD changes are safe)
3. Amend each repo: `cd <repo> && git add -A && git commit --amend --no-edit`

Then retry: `p8 publish --no-unit-test --no-iwyu`

## Commit Message Format

```
[MODULE] English one-line summary

中文详细说明（高层次描述，不要太细）：
* 要点一
* 要点二
```

**Rules:**
1. **MODULE**: `[LIO]`, `[NAVIS]`, `[MSL]`, etc. - infer from file paths
2. **First line**: English, imperative mood ('Add', not 'Added')
3. **Body**: 中文 bullets，高层次描述 WHAT + WHY，代码/变量名用 markdown 格式（反引号）

**写法原则：**
- 描述"做了什么"而不是"改了哪些文件"
- 一个要点对应一个功能/概念，不要逐行解释
- 代码符号用反引号：`ClassName`、`function_name`、`FLAGS_xxx`
- 公式用 LaTeX：`$x^2$`

**Bad Example (太细):**
```
- Add DynamicProjection class with Eigen-based coordinate conversion APIs
- Extend StampedConstMsgPtr to support proto value types (not just SharedPtr)
- Convert LFM and GNSS buffers to store proto values for projection support
- Integrate DynamicProjection into NavisWorld for LFM, GNSS, and Localizer conversion
- DynamicProjection internally handles is_enabled() check (no-op when disabled)
- Update downstream PU access patterns from .data()-> to .data().
```

**Good Example (高层次):**
```
[NAVIS] Add dynamic projection support for localization data

- 增加 `DynamicProjection`，在 `FLAGS_localizer_internal_use_dynamic_origin` 为 true 时初始化 Dynamic Projection，转换 Position/Velocity/Orientation；为 false 时调用转换函数不生效
- `NavisWorld` 增加 `DynamicProjection`，目前转换 LFM、RTK 和 Localizer
- buffer 中不再存储 `framework::MessageSharedPtr`，而是直接存储 proto，修改下游 PU 适配这个变化
```

## Starting a New Branch

### Step 1: Check State
```bash
p8 status
```

### Step 2: Handle Uncommitted Changes
```bash
p8 stash -m <descriptive_name>
```

### Step 3: Start Branch
```bash
# Based on master
p8 start <branch_name>

# Based on release
p8 start <branch_name> --base-branch release_v2_YYYYMMDD
```

### Step 4: Restore Stash (if applicable)
```bash
p8 stash --pop
```

## Pre-Publish Lint Fixes

### cpp_lint: Line Length > 100
```bash
clang-format-13 -i path/to/file.cc
```

### sort_include: Include Order
```bash
mpm install sort_include
sort_include path/to/file.h
```

### gflags_lint: Invalid DECLARE/DEFINE
- `DEFINE_xxx` only in `.cc` files
- `DECLARE_xxx` only in corresponding `.h` files

Find correct header:
```bash
grep -r 'DECLARE_bool(some_flag)' --include='*.h' .
```

Replace `DECLARE_xxx` with `#include "path/to/header.h"`

**In tests, use:** `google::SetCommandLineOption("flag_name", "value")`

### Complete Lint Fix Flow
```bash
clang-format-13 -i path/to/*.cc path/to/*.h
mpm install sort_include && sort_include path/to/file.h
cd /path/to/repo && git add -A && git commit --amend --no-edit
p8 publish --no-unit-test --no-iwyu
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Forgot sync before publish | Run `p8 sync` first |
| Wrong base-branch | `p8 publish --base-branch <correct>` |
| IWYU keeps failing | Run `clang-format-13 -i` |
| Uncommitted changes block start | `p8 stash -m <name>` |
| First-time publish without --create-pr | Retry with `--create-pr --pr-title="..."` |

## Handling Sync Conflicts

### Resolve and Continue
```bash
cd <conflicting_repo>
# Edit files to resolve
git add .
git rebase --continue
```

### Abort
```bash
p8 gitall -c rebase --abort
```

---
name: working-with-multi-git-subrepos
description: Use when a monorepo contains multiple nested Git repositories and git commands give confusing results because you are in the wrong repo directory.
---

# Working with Multiple Git Sub-Repos in a Monorepo

## Overview
This codebase is a monorepo that contains multiple *independent* Git repositories. **Git commands act on the repository that contains your current working directory.** If you run `git` from the wrong folder, you will inspect/commit the wrong repo.

## When to Use
- `git status` looks “clean” but you *know* you changed files.
- `git log` / `git branch` doesn’t show the history you expect.
- `git diff` shows unrelated changes or nothing at all.
- You need to commit changes under a subdirectory like `map/`, `common/`, etc.

## Core Rules
1. **Always confirm which repo you are in before doing anything destructive.**
   - `git rev-parse --show-toplevel`
2. **Run Git commands inside the correct sub-repo.**
   - Either `cd` into that sub-repo, or use `git -C <path>`.
3. **Treat each sub-repo as its own unit.**
   - Separate branches, remotes, commit history, and PRs.

## Quick Reference

### Identify the active repo (must-do sanity check)
- Show repo root for your current directory:
  - `git rev-parse --show-toplevel`
- Show status with branch info:
  - `git status -sb`

### Run Git without changing directories
Use `git -C` to avoid “wrong CWD” mistakes:
- `git -C map status -sb`
- `git -C map diff`
- `git -C map log --oneline -n 20`

### Find candidate sub-repos
From the monorepo root, list immediate child directories that *look like* Git repos:
- `for d in */; do [ -e "${d}.git" ] && echo "$d"; done`

If repos are nested deeper, search for `.git` entries:
- `find . -maxdepth 4 -name .git -o -name .gitmodules 2>/dev/null`

### Safe commit checklist (per sub-repo)
Inside the right repo root:
- `git status -sb`
- `git diff`
- `git add -p`
- `git commit -m "<message>"`

## Common Mistakes (and how to stop making them)

### Mistake: Running `git` from the monorepo root
Symptom: `git status` doesn’t show your edits.
Fix: `cd` into the sub-repo that owns the files, or use `git -C <subrepo>`.

### Mistake: Committing changes across different sub-repos together
Symptom: commit contains unrelated paths, or you can’t push/PR cleanly.
Fix: keep commits scoped to a single sub-repo. Split work across repos.

### Mistake: Assuming all directories share one remote
Symptom: `git push` fails or pushes to an unexpected remote.
Fix: check `git remote -v` in the *current* repo root.

## Related Project Constraints
- This is a Bazel-based codebase. For Bazel commands, follow project rules (e.g., use remote config and optimized mode when required by the repo’s guidelines).

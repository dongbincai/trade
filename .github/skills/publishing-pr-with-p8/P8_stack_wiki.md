# P8 Stack 使用指南

## 概述

为了方便代码评审（review）和能够快速回退（revert）有问题的 PR，我们鼓励用户将大的修改（上百行的行修改或者过多的文件修改）拆成多个小的修改分别发出 PR，并且依次合并（merge）。

然而 p8 的 base branch 并不完全支持这种做法，因此我们推出了 p8 stack 的功能，让用户可以在一个本地分支上堆叠分支，并且用 p8 命令管理和发布这些分支到 GitHub 上创建 PR。这些 PR 仅有对应分支的修改，方便 reviewer 只评审自己关心的代码，同时用户可以在这些分支的 PR 上运行 CI workflow！

**当前限制：**
- 只支持用户本地 stack 堆叠 branch，不支持多用户之间共享 branch 协作开发
- 目前 stack branch 只支持常用的 CI workflow 和 bet/brt workflow，如果有其他 workflow 需求请联系 @光煦灿

## 使用准备

请安装最新版本的 p8：
```bash
mpm upgrade pony-repo
```

## 命令介绍

p8 stack 支持 master 和任意的 release_v2 分支，下文命令中的 master 可以替换成 release 分支。

### 创建分支

**`p8 stack start <branch_name>`**：基于当前本地分支创建 stack branch

该功能不同于 `p8 start`，不支持 `--remote-branch` 和其他参数，只能基于当前 branch 创建。

若想使用 `p8 start` 的 flag，请参阅 [p8 stack rebase](https://ponyai.feishu.cn/wiki/GFjowsgfAixZqkkJVDacPqX5nLg#share-QVlhdkh1eozQI4xBi8ic6pLZnKf) 命令先 `p8 start` 再 `p8 stack rebase` 叠到本地 branch。

**示例**（第一个分支需要用 `p8 start` 创建）：
```bash
$ p8 start feature_1 --base-branch master
# coding ...
# $ p8 stage && p8 commit
$ p8 stack start feature_2
# coding ...
# $ p8 stage && p8 commit
$ p8 stack start feature_3
```

### 查询分支情况

**`p8 stack list`**：查询当前分支所在 stack 的情况。

**`p8 stack list -a/--all`**：查询所有分支的 stack 情况。

**示例**：
```bash
$ p8 stack list
feature_1 (based on ponyai/master) (modified repos: ['common'])
└── feature_2 (modified repos: ['common'])
    └── featuer_3 (modified repos: ['common'])

$ p8 checkout random_branch
$ p8 stack list -a
feature_1 (based on ponyai/master) (modified repos: ['common'])
└── feature_2 (modified repos: ['common'])
    └── featuer_3 (modified repos: ['common'])
```

### 发布分支

**`p8 publish`**：可以在 stack branch 上运行，仅发布当前的 branch。

生成的 PR 仅可用来 review 和运行 CI workflow，不要手动 merge，直接 merge 也不会 merge 到前置的 branch。

**示例**：
```bash
$ p8 checkout feature_2
$ p8 publish
```
生成了 [PR](https://github.corp.pony.ai/ponyai2/common/pull/118113)，该 PR 是基于 feature_1 分支的 feature_2 的代码，只有 feature_2 branch 的修改，用户可以在 PR 上评论 Jenkins 命令触发 CI workflow。

**`p8 stack publish`**：一次性推送当前 stack 里的所有 branch。

**可选参数：**
- `--no-update-root`：不推送第一个 branch（示例中的 feature_1）
- 还有其他参数和 `p8 publish` 相同，可以用 `--help` 查询

**示例**：
```bash
$ p8 stack publish
# 示例输出
# Now switch to branch feature_1 and publishing ...
# ...
# Done publishing branch feature_1.
# Now switch to branch feature_2 and publishing ...
# Done publishing branch feature_2.
# Now switch to branch featuer_3 and publishing ...
# Done publishing branch featuer_3.
```

### 更新分支

**`p8 sync`**：将前置的 branch 的修改更新到当前 branch（仅应用前置 branch 的修改，而不是所有的前置 branch）。

如果 feature_1 有修改，在 feature_3 上 sync 是不会 apply 的，此时需要下面的 `p8 stack update` 命令。

不支持 `p8 sync --base-branch` 重新指定 base branch。

**示例**：
```bash
$ p8 checkout feature_3
$ p8 sync
# 将本地的 feature_2 的更新应用到 feature_3
# 示例输出：
# Successfully sync to feature_3|feature_2|master
```

**`p8 stack update`**：依次更新当前 stack 里的所有 branch，例如示例先更新 feature_1 到最新的 master，再更新 feature_2 到 feature_1，再更新 feature_3 到 feature_2。

**可选参数：**
- `--no-update-root`：不更新第一个 branch（示例中的 feature_1，例如某些情况下不想更新到最新的 master）
- 还有其他参数和 `p8 sync` 相同，可以用 `--help` 查询

**示例**：
```bash
$ p8 checkout feature_2
$ p8 stack update
# 更新 stack 里所有的 branch，包括 featue_1（会 sync 到 master）

$ p8 stack update --no-update-root
# 不想更新到最新的 master，只更新本地分支的代码
```

**注意：** 如果更新分支时有 conflict，请解决冲突并且运行 `git rebase --continue`，目前 stack branch 不支持 abort 操作。

### 删除分支

**`p8 abandon <branch>`**：支持删除 stack branch

不会更新其他 branch，更新其他 branch 需要用户手动执行 `p8 sync` / `stack update`（例如删除 feature_2，feature_3 会叠到 feature_1 上）。

**常见用途：**
1. 丢弃不想用的 stack branch（慎重，后续 branch 会自动叠加到前置的 branch 上，`p8 sync` / `stack update` 可能会有冲突）
2. 当第一个 branch 在 GitHub 上 merge 的时候，使用 `p8 abandon` 丢弃该分支，`p8 sync` / `stack update` + `p8 publish` 即可更新后续的 branch 对应的 PR

**示例**：
```bash
$ p8 abandon feature_1
$ p8 checkout feature_2
$ p8 sync
# 示例输出：
# The previous branch feature_1 do not exist locally, rebase feature_2 onto master.
# ...
# Successfully rebased and updated refs/heads/feature_2.

$ p8 publish
# 示例输出
# ...
# Finish branch pushing.
# Pull request for project 'common' from branch 'feature_2' already exists. https://github.corp.pony.ai/ponyai2/common/pull/118113
# However the base of https://github.corp.pony.ai/ponyai2/common/pull/118113 is xucan_feature_2|feature_1|master, would change to master
# ...
```
此时 feature_2 的 PR 的 base 已经更新为 master。

### 迁移分支

**`p8 stack rebase <another_branch/remote_branch>`**：将当前 branch 叠加到另一个 branch 上，也可以 rebase 回某个 base branch。

迁移分支后重新 publish，如果该 branch 已经有对应的 PR，p8 不会创建新的 PR 而是修改已有 PR 的 base，因此不会担心 review comment / check 的丢失。

**示例**：
```bash
$ p8 stack list
# 示例输出：
# feature_1 (based on ponyai/master) (modified repos: ['common'])
# └── feature_2 (modified repos: ['common'])

$ p8 start feature_1_1 --base-branch master
$ p8 stack rebase feature_1

$ p8 stack list
# 示例输出：
# feature_1 (based on ponyai/master) (modified repos: ['common'])
# ├── feature_1_1 (modified repos: [])
# └── feature_2 (modified repos: ['common'])
# 可以看到已经叠到 feature_1 分支上

# 再 rebase 回 master
$ p8 stack rebase ponyai/master
# 示例输出：
# Now rebasing feature_1_1 onto base branch ponyai/master...
# Successfully rebased and updated refs/heads/feature_1_1.
```

**另一个用法**：可以在一个新的 workspace 里复现 PR 并开发，例如用户有一个 PR 分支为 `user_feature_2`，base 为 `user_feature_1`，可以在本地另一个 workspace 里复现这个 PR 继续开发：
```bash
$ p8 start user_feature_1
$ p8 start user_feature_2
$ p8 stack rebase user_feature_1
# do changes
$ p8 publish # 此时会推送到该 PR 上
```

### 合并分支

stack branch 需要按顺序合并。

在上述例子中，将 base master 的 feature_1 的 PR merge 之后，用户需要在本地 [abandon feature_1 分支并且 sync feature_2 分支](https://ponyai.feishu.cn/wiki/GFjowsgfAixZqkkJVDacPqX5nLg#share-LmR7d8gc3ol1Moxol1NcImXXn7b)，p8 会自动帮你将 feature_2 rebase 到 master，或者也可以用 `p8 stack rebase` 命令手动 rebase。rebase 之后运行 `p8 publish` 更新 PR，这样 PR 才能正确的 merge 进 master。

**重要提示：** 不要在没有 rebase 的 stack branch 的 PR 页面点击 squash and merge 或者运行 jenkins combo / merge 命令！

**方法一：使用 `p8 stack rebase`**
```bash
# feature_1 分支已经 merge
p8 checkout feature_2
p8 stack rebase ponyai/master # 此时 feature_2 的 base branch 会切换成 master
p8 publish # 此时 PR 的 base 会切换成 master
# 在 PR 页面上运行 jenkins combo basic 命令 merge 即可
```

**方法二：使用 `p8 abandon + sync`**
```bash
# feature_1 分支已经 merge
p8 checkout feature_2
p8 abandon feauture_1 
p8 sync # 此时 feature_2 的 base branch 自动切换成 master 并且 sync master
p8 publish # 此时 PR 的 base 会切换成 master
# 在 PR 页面上运行 jenkins combo basic 命令 merge 即可
```

## 一个简单的使用场景

```bash
p8 start branch_A --base-branch master
# modify and add files
p8 stage && p8 commit
p8 stack start branch_B
# modify and add files
p8 stage && p8 commit

p8 stack publish # 发布 branch_A 和 branch_B

# 发现 branch_A 的 PR 上有 review，需要修改
p8 checkout branch_A
# resolve comments
p8 stack update # 更新 branch_A 和 branch_B
p8 stack publish

# 在 branch_A 上运行 jenkins combo basic
# branch_A 已经 merge 了
p8 abandon branch_A
p8 checkout branch_B
p8 sync # 自动将 branch_B 切回 master
p8 publish # 发布的 PR 的 base 也变回 master

p8 stack start branch_C
#...
```

## 拆解现有的大 PR

假如用户 xucan 现在已有一个很大的 PR，对应的远程分支为 `xucan_fix`，base branch 是 master，现在想用 p8 stack 功能拆解这个 PR 为多个小的 PR，可以借用 `git cherry-pick` 和 `git checkout` 命令：

### 以 commit 为单位进行拆分

这种方法比较适合于用户在已有的分支上已经用多个 commit 标记了 change，可以直接基于 commit 拆分：

```bash
p8 fetch xucan_fix # 注意有 username 前缀
# 假设 xucan_fix 在 common 有两个 commit，分别是 commit_1 和 commit_2，在 sensors 有一个 commit_3

# 首先起一个新的 branch，只有 common 的 commit_1 和 sensors 的 commit_3 修改
p8 start branch_A --base-branch master # master 请根据情况替换成对应的 base branch
git -C common cherry-pick commit_1
git -C sensors cherry-pick commit_3
# 可能需要解 cherry-pick 带来的 conflict

# 再起一个 branch，加上 common 的 commit_2
p8 stack start branch_B
git -C common cherry-pick commit_2
```

### 以文件为单位进行拆分

如果用户在之前的分支上就没有使用 commit 进行管理，也可以基于文件进行拆分，建议将文件尽可能的细化成单个文件：

```bash
p8 fetch xucan_fix # 注意有 username 前缀
# 假设 feature_big 在 common 有两个文件夹的修改，分别是 tools/tool_1 和 utils/util_2，在 sensors 有一个 tools/tool_3 的文件夹修改

# 首先起一个新的 branch，只修改 tools/tool_1
p8 start branch_A --base-branch master # master 请根据情况替换成对应的 base branch
git -C common checkout ponyai/xucan_fix tools/tool_1 # xucan_fix 前需要加上 ponyai/ 前缀
p8 stage -A && p8 commit

# 再起一个 branch 拆分 common 的修改
p8 stack start branch_B
git -C common checkout ponyai/xucan_fix utils/util_2
p8 stage -A && p8 commit

# 再起一个分支描述 sensors 的修改
p8 stack start branch_C
git -C sensors checkout ponyai/xucan_fix tools/tool_3
p8 stage -A && p8 commit
```

## P8 实现简介

### Stack Upstream 隔离

为了保证每个 stack branch 是独立的，并且可以正常运行 `p8 diff` 等命令与前置 branch 进行比对，我们对每个 stack branch 额外维护了一个 upstream。

例如有一个本地分支 `feature_1`，当使用 `p8 stack start` 命令在该分支上创建新分支 `feature_2` 的时候，p8 会：
1. 先从 `feature_1` 中创建一个 `feature_2|feature_1|master` 的分支
2. 再创建一个 `feature_2` 分支

这样做可以将 `feature_2` 和 `feature_1` 进行分离，修改了 `feature_1` 也不会直接影响 `feature_2`。另外在 publish 的时候将 `feature_2|feature_1|master` 和 `feature_2` 同步推送，创建的 PR 的 base 是 `feature_2|feature_1|master`，这样创建的 PR 不会因为 `feature_1` 的改动而改变内容。
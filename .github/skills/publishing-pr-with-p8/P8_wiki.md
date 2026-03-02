# P8 wiki

## 概念介绍

### P8 是什么？

由于 git 只能用来管理单个仓库，而我们常用的仓库有 common / map / pnc / ... 等多个仓库，因此我们开发了 p8 (pony-repo) 作为多仓库的管理工具，方便我们进行管理。

p8 基本操作和 git 简介请参考 [【2024】Onboard Training - First PR - Tools setup & Engineering practice.pptx](https://ponyai.feishu.cn/file/YiycbqnHVorkoxxA1n5cATHanhc)

### Pony branch id 是什么？

Pony branch id 是 ponyai 用来给多仓库记录版本所用，类比单仓库的 git commit。

Git 使用 commit 管理单个仓库，p8 管理多个仓库的时候需要保证每个仓库的 commit 是一致的，比如某个用户在多个仓库创建了同一个 branch 和多个 PR，并且merge 进 master，这时候我们会给这些 PR的 description 中记录一个一致的 pony branch id 作为记号，以后用户可以直接通过 p8 start 等命令通过 --pony-branch-id 指定这个 pony branch id 对应的多个 commit 同时进行操作。

Pony branch id 可以用在 p8 的很多命令中，你可以使用 --help 查看该命令支持的参数，例如 p8 start --help。

```bash
p8 start local_branch --pony-branch-id c89128706e829c16f2d15e887dd7fbd5d0aeb869
p8 cherry-pick 847c17e0b5e70d929428ec43a099efe67afd3da5
p8 sync --pony-branch-id 847c17e0b5e70d929428ec43a099efe67afd3da5
```

### p8 的 base_branch 和 remote_branch 是什么？

p8 是基于 git 和 github 管理分支也就是 branch 的，我们默认都是基于 master branch进行开发，同时我们还有不同的 release 开发版本，这些 release 开发版本对应的分支一般都是 release_v2_* 的格式。

如果想要对某个远程分支 A （常见的场景如 master 或 release branch release_v2_*) 进行 commit ，这个时候需要基于分支 A 起一个新的branch B，并且发布 PR merge 进这个分支A，这时候 A 就是 B 的 base branch。

```bash
p8 start branch_B --base-branch branch_A
```

下图示例是 一个 PR 标题下方信息的截图，表明远程分支 xucan_fix_stack_start 想要 merge 进 master，那么 master 就是 xucan_fix_stack_start 的 base branch。

有时候，我们并不想修改远程分支 branch B，而是复制其 commit (例如用别人代码来部署或者debug）来开一个新的 branch C，这个时候 branch B 作为 remote branch 即可，没有指定 --base-branch 会默认 master 作为 base branch。如果要复制的 branch B 是基于 branch A 的，请将新的 branch C 设置同样的 base branch（否则发出来的 PR 上默认基于 master，会多出来很多 diff commit！）

```bash
p8 start branch_C --remote-branch branch_B --base-branch branch_A
# 含义是从 branch_B 复制一个 branch_C 出来，准备 merge 到 branch_A
```

如果 branch_C 和 branch_B 同名且 branch_B 的前缀是你的 username，那么 publish branch_C 的时候直接推送到远程分支 branch B。

### Cherry-pick 是什么？

有时我们想把 master 上的某些 commit 复制到 release branch 上，或者反过来，这个时候由于 master 和 release branch 的文件是不一样的，需要用到 p8 cherry-pick。不同于 git cherry-pick 使用的是 commit hash，而 p8 cherry-pick 使用的是 pony branch id。

```bash
p8 start cp_branch --base-branch release_v2_20241231
p8 cherry-pick <pony_branch_id> --base-branch master
# 或者反过来
p8 start cp_branch --base-branch master
p8 cherry-pick <pony_branch_id> --base-branch release_v2_20241231
```

如果想 cp 还没有 merge 的 pr，请用 git cherry-pick --pick-branch 命令。示例：

```bash
p8 start test_cp --base-branch release_v2_20250520
p8 cherry-pick --pick-branch xucan_change_0101 --base-branch release_v2_20250101
# 在 0520 分支上 cp xucan_change_0101（based on 0101) 的 change
```

## 操作介绍

基本的 checkout / start / publish / sync 等操作可以参考 [【2024】Onboard Training - First PR - Tools setup & Engineering practice.pptx](https://ponyai.feishu.cn/file/YiycbqnHVorkoxxA1n5cATHanhc)，此处不再重复介绍。

### p8 cherry-pick 或者 p8 sync 失败怎么办

p8 sync 会 fetch 最新的 base branch 并且将你本地的 commit apply 上去，如果此时你本地的 commit 和 base branch 新进的 commit 有冲突，p8 sync 就会失败，并且提示你需要 resolve conflict。

此时你有两个选择：

1. **解决冲突后继续sync**：你需要根据 log 中的提示对 CONFLICT 的文件进行修改，修改完成后进入报错的仓库执行 git 命令：

```bash
cd common # common 为示例，请替换成实际报错的 repo
git add .
git rebase --continue
# 如果有多个仓库冲突，请使用上述指令依次解决冲突
p8 status # 此时应该可以看到所有的仓库都是正常状态，没有 (detached) (under_rebase) 这样的仓库
```

2. **回退，不sync**：执行 p8 gitall -c rebase --abort 即可，此时会将有冲突的仓库回退到之前的版本。

p8 cherry-pick 也是一样，不同的是需要将 git rebase --continue 替换成 git cherry-pick --continue，p8 gitall -c rebase --abort 替换成 p8 gitall -c cherry-pick --abort。

### 如何分拆大的 PR

如果一个 PR 太大，会影响 review，同时过多的代码也容易出 bug，有问题需要全部 revert，因此在开发时我们推荐将一个大的 PR 拆成多个小的 PR 分开 review，可以用 p8 stack 系列命令：[P8 stack 使用指南](https://ponyai.feishu.cn/wiki/GFjowsgfAixZqkkJVDacPqX5nLg)来堆叠小的分支。

### 新增或者删除仓库

p8 会帮您同时管理多个仓库，但是添加新的仓库后，您需要手动在新的仓库中创建已有的分支：

```bash
# 可以先 p8 config --show 检查 project_list 看看本地已有的仓库
p8 config -g common,pnc,...
# 如果是新增仓库，此时本地已有的 branch 在 新仓库中不存在，需要进行以下操作
# 重新start 一个新的 branch，可以设置一个临时的名称
p8 start <branch_to_start>
# 现在再切换到之前的 branch
p8 checkout <old_branch> --auto-create-branch
```

p8 config -g 参数后面接上你想重新设置workspace 所拥有的仓库，注意需要包括本地已有的仓库，例如你本地已有 common,map,perception 仓库，现在想增加 pnc 仓库删除 map 仓库，那么命令应该是 p8 config -g common,pnc,perception。

-g auto 会自动设置所有有权限的仓库：

```bash
p8 config -g auto
# 同样支持 p8 init: p8 init -g auto
```

### 我想切换新的 base branch

如果您有一个分支是基于 master，此时想将 commit 挪到某个 release 分支 release_v2_20250101 上，可以直接使用 p8 sync --base-branch release_v2_20250101 进行切换。或者您不想切换本地分支，只想发一个基于 release_v2_20250101 的 PR ，可以使用 p8 publish --base-branch release_v2_20250101 命令。

### [进阶] 我想链接一个新的 workspace

如果您已经有一个 workspace，想新开一个 workspace ，但是又想减少磁盘占用，您可以使用 git worktree 功能来基于现有的 workspace 来"链接"创建一个新的 workspace，创建出来的 workspace 和之前的 workspace 共享 branch list，但是可以分别在不同的 branch 上操作，一个操作示例如下：

```bash
# 假设已有一个workspace 是 ~/work/ponyai/.sub-repos
# 现在我想克隆一个 workspace 到 ~/work/ponyai2/.sub-repos

mkdir ~/work/ponyai2 && cd ~/work/ponyai2
repos="common,os-environment"
# 请与你想克隆的 workspace config 保持一致，例如你的 ~/work/ponyai 只有 common repo,其他为 interface repos, 此时 repos="common"，具体配置可以在 ~/work/ponyai 下运行 p8 config --show 查看
# 你可以设置不同的 workspace repo config，但是这样 p8 就不能在多个 workspace 之间任意checkout branch 了
p8 init -g $repos
for d in ${repos//,/ }; do rm -rf .sub-repos/$d; done

cd ~/work/ponyai/.sub-repos
for d in ${repos//,/ }; do d=${d%/}; if [ -d "$d/.git" ] || [ -f "$d/.git" ]; then git -C "$d" worktree add -d ~/work/ponyai2/.sub-repos/"$d"; fi; done

cd ~/work/ponyai2/.sub-repos
p8 sync
p8 branch # 现在你可以看到 ponyai2 和 ponyai 共享 branch list
p8 start <new_branch> # 你可以新建一个branch 在 ponyai2 进行开发，ponyai 和 ponyai2 互不干扰

# du -d 1 ~/work -h
# 26G        ./ponyai
# 3.2G        ./ponyai2
# 可以看到 ponyai2 磁盘占用并不高

# 如果你不想要链接了，可以运行以下命令清理
rm -rf ~/work/ponyai2
cd ~/work/ponyai/.sub-repos
p8 gitall -c worktree prune
# 用这个命令可以看当前链接的 workspace
# git -C common worktree list -v
# /home/xucan/work/ponyai/.sub-repos/common   xxx
# /home/xucan/work/ponyai2/.sub-repos/common  xxx
```
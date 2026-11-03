# project-kickoff

一个适配 Codex 的项目开工技能，用根目录 `AGENTS.md` 作为工作入口，在 `.project/` 保存稳定项目事实、当前进度、重要变更记录与必用产物版本工具。

## 安装

将本仓库放入 Codex 技能目录：

```powershell
$target = Join-Path $HOME '.codex\skills\project-kickoff'
git clone https://github.com/360867033/project-kickoff.git $target
```

仓库根目录就是技能目录，根目录的 `SKILL.md` 作为入口；安装后按实际环境刷新技能列表。

## 功能

- 初始化根 AGENTS 的受标记区块，保留其他指令与换行。
- 创建 `.project/PROJECT.md`、`.project/PROGRESS.md` 和 `.project/scripts/_version.py`，不扫描项目文件。
- PROJECT 维护稳定目标、范围与完成条件；PROGRESS 同页维护当前进度、完成证据、阻塞、下一步和重要变更。
- 开始任务默认只读当前进度，追溯时再读历史；实质变化才更新并带用户时区日期，不逐条回复记日志。
- 项目脚本统一放在 `.project/scripts/`；项目级技能放在 `.project/skill/<技能名>/`，自带资源随技能保存，按需创建并记录实际加载入口。
- 版本规则与 `.project/scripts/_version.py` 工具入口只写入 AGENTS，PROJECT 不重复；AGENTS 不加入通用文件检索提示。正式交付产物必用 `名称_v主.次_YYYYMMDD.ext`，new 只计算路径，生成并验证后 register，latest / versions 查询历史。
- 默认只预览，`--apply` 才写入；支持备份、幂等刷新和显式旧记录迁移。

## 快速使用

```powershell
python "$HOME\.codex\skills\project-kickoff\scripts\init_workspace.py" 'C:\path\to\project' --name '项目名' --goal '项目目标'
# 核对预览后加 --apply
```

## 旧项目升级

有旧 `.project/CHANGELOG.md` 时，初始化和 register 停止；明确迁移指定项目：

```powershell
python "$HOME\.codex\skills\project-kickoff\scripts\init_workspace.py" 'C:\path\to\project' --migrate-changelog
# 核对预览后加 --apply
```

完整原文收纳到 PROGRESS 的只读历史围栏，原字节保留为 `CHANGELOG.md.history_<摘要>`；原活动 CHANGELOG 退役。内容 SHA-256 标记保证幂等，保留既有当前进度和产物事件标识；同时备份并刷新项目版本模块，保留 PROJECT 的业务事实。

已使用 PROGRESS 的旧项目，仅升级版本模块：

```powershell
python "$HOME\.codex\skills\project-kickoff\scripts\init_workspace.py" 'C:\path\to\project' --refresh-version-tool
# 核对预览后加 --apply
```

agent 在授权内备份后定向更新旧 PROJECT 导航、重复动态状态与过时约定，保留稳定业务事实。版本规则集中到 AGENTS 后，定向移除 PROJECT 的重复通用版本管理段并保留独立脚本位置；初始化器默认保留已有 PROJECT，不自动清理。旧管理资料退出活动目录前核对备份，不批量处理其他项目。register 仅追加重要变更，不改写当前进度；旧 publish 分类操作零写拒绝。`--force` 会刷新 PROJECT 与版本模块，单独升级工具使用窄范围刷新选项。

## 验证

```powershell
python -m unittest discover -s "$HOME\.codex\skills\project-kickoff\scripts" -p 'test_*.py' -v
```

技能自身发布历史见仓库 `CHANGELOG.md`，与生成项目的 PROGRESS 职责不同。

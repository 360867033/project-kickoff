# project-kickoff

一个适配 Codex 的项目开工技能，用根目录 `AGENTS.md` 作为入口，以及 `.project/` 保存项目事实、当前进度、重要变更记录与版本工具；文件关系索引按需启用。

## 安装

将本仓库放入 Codex 技能目录：

```powershell
$target = Join-Path $HOME '.codex\skills\project-kickoff'
git clone https://github.com/360867033/project-kickoff.git $target
```

仓库根目录就是 Codex 技能目录，根目录的 `SKILL.md` 会被 Codex 读取。安装后重启 Codex 或刷新技能列表，使新技能生效。

## 功能

- 初始化根目录 `AGENTS.md` 的受标记区块，不覆盖原文件其他指令。
- 默认创建 `.project/PROJECT.md`、`.project/PROGRESS.md` 和 `.project/scripts/_version.py`；不初扫项目，不创建 MAP。
- 明确需要文件索引时加 `--with-map`；已有 MAP 保留，按需读取与登记。
- 项目目标、范围与完成条件等稳定事实写入 PROJECT；PROGRESS 同页维护当前进度、完成证据、阻塞、下一步和重要变更。AGENTS 仅作简短读取/更新指引。
- 开始项目任务默认只读 PROGRESS 的当前进度，追溯时再读历史；阶段成果、阻塞或下一步有实质变化才更新并标用户时区日期，不逐条回复记日志。
- 项目级技能存放在 `.project/skill/<技能名>/`，以 `SKILL.md` 为入口，技能自带资源随技能保存；按需创建，实际加载入口按运行环境配置。
- 独立项目脚本统一存放在 `.project/scripts/`。正式交付产物使用 `名称_v主.次_YYYYMMDD.ext`，版本管理为必用项。
- 默认只预览，使用 `--apply` 才写入。支持备份、幂等刷新、只读索引巡检及产物版本登记。

## 快速使用

```powershell
python "$HOME\.codex\skills\project-kickoff\scripts\init_workspace.py" 'C:\path\to\project' --name '项目名' --goal '项目目标'
python "$HOME\.codex\skills\project-kickoff\scripts\init_workspace.py" 'C:\path\to\project' --name '项目名' --goal '项目目标' --apply
# 仅需要索引核对时运行 doctor；无索引不算故障
python "$HOME\.codex\skills\project-kickoff\scripts\doctor.py" 'C:\path\to\project' --json
```

## 旧项目迁移与版本登记

若目标项目仍有 `.project/CHANGELOG.md`，初始化器和 register 会停止。明确迁移该项目时：

```powershell
python "$HOME\.codex\skills\project-kickoff\scripts\init_workspace.py" 'C:\path\to\project' --migrate-changelog
# 核对预览后加 --apply；需要新建索引时另加 --with-map
```

迁移将完整原文收纳到 PROGRESS 的只读历史区域，原字节保留为 `CHANGELOG.md.history_<摘要>`，原活动 CHANGELOG 退役；按 SHA-256 标记避免重复迁入，保留既有当前进度及产物事件标识。迁移同时备份并刷新项目版本模块，保留 PROJECT 的业务事实；已有 PROJECT 的旧导航及重复动态状态由 agent 备份后定向更新，旧 CHANGELOG 不再作为活动入口。旧发布分类只作历史文字。只迁移指定项目，不扫描或修改其他业务项目。

`register` 只登记已生成且已验证的版本产物，写入 PROGRESS 的重要变更；无 MAP 也能执行，有 MAP 时沿用文件/目录去重规则，不改写当前进度。`new` 仍只计算路径，`latest` / `versions` 保留。未发布/已发布分类及 `publish` 操作已移除，旧命令零写拒绝。`--force-data` 仅在 `--with-map` 时刷新 MAP，不清空进度或历史。

## 验证

```powershell
python -m unittest discover -s "$HOME\.codex\skills\project-kickoff\scripts" -p 'test_*.py' -v
```

版本记录见 `CHANGELOG.md`。

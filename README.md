# project-kickoff

一个适配 Codex 的项目开工技能，用根目录 `AGENTS.md` 作为入口，以及 `.project/` 保存项目事实、文件关系、变更记录与版本工具。

## 安装

将本仓库中的技能文件放入 Codex 技能目录：

```powershell
$target = Join-Path $HOME '.codex\skills\project-kickoff'
New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
Copy-Item -LiteralPath '.\project-kickoff' -Destination (Split-Path -Parent $target) -Recurse -Force
```

仓库同时提供根目录与 `project-kickoff/` 两种布局：

- 下载完整仓库并安装时，复制 `project-kickoff/` 子目录。
- 将本仓库直接放在 `~/.codex/skills/project-kickoff` 时，根目录的 `SKILL.md` 即可被 Codex 读取。

根目录的 `SKILL.md` 与子目录中的文件由同一份 v0.9.2 技能同步生成，校验时逐文件比对 SHA256。

## 功能

- 初始化根目录 `AGENTS.md` 的受标记区块，不覆盖原文件其他指令。
- 创建 `.project/PROJECT.md`、`.project/MAP.md`、`.project/CHANGELOG.md` 和 `.project/scripts/_version.py`。
- 项目目标、阶段与完成条件写入 PROJECT；文件上下游关系写入 MAP；变更写入 CHANGELOG。AGENTS 仅作简短导航。
- 脚本统一存放在 `.project/scripts/`。正式交付产物使用 `名称_v主.次_YYYYMMDD.ext`，版本管理为必用项。
- 默认只预览，使用 `--apply` 才写入。支持备份、幂等刷新、只读索引巡检及产物版本登记。

## 快速使用

```powershell
python .\project-kickoff\scripts\init_workspace.py 'C:\path\to\project' --name '项目名' --goal '项目目标'
python .\project-kickoff\scripts\init_workspace.py 'C:\path\to\project' --name '项目名' --goal '项目目标' --apply
python .\project-kickoff\scripts\doctor.py 'C:\path\to\project' --json
```

## 验证

```powershell
python -m unittest project-kickoff\scripts\test_smoke -v
```

版本记录见 `CHANGELOG.md`。
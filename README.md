# project-kickoff

一个适配 Codex 的项目开工技能，用根目录 `AGENTS.md` 作为入口，以及 `.project/` 保存项目事实、文件关系、变更记录与版本工具。

## 安装

将本仓库放入 Codex 技能目录：

```powershell
$target = Join-Path $HOME '.codex\skills\project-kickoff'
git clone https://github.com/360867033/project-kickoff.git $target
```

仓库根目录就是 Codex 技能目录，根目录的 `SKILL.md` 会被 Codex 读取。安装后重启 Codex 或刷新技能列表，使新技能生效。

## 功能

- 初始化根目录 `AGENTS.md` 的受标记区块，不覆盖原文件其他指令。
- 创建 `.project/PROJECT.md`、`.project/MAP.md`、`.project/CHANGELOG.md` 和 `.project/scripts/_version.py`。
- 项目目标、阶段与完成条件写入 PROJECT；文件上下游关系写入 MAP；变更写入 CHANGELOG。AGENTS 仅作简短导航。
- 脚本统一存放在 `.project/scripts/`。正式交付产物使用 `名称_v主.次_YYYYMMDD.ext`，版本管理为必用项。
- 默认只预览，使用 `--apply` 才写入。支持备份、幂等刷新、只读索引巡检及产物版本登记。

## 快速使用

```powershell
python "$HOME\.codex\skills\project-kickoff\scripts\init_workspace.py" 'C:\path\to\project' --name '项目名' --goal '项目目标'
python "$HOME\.codex\skills\project-kickoff\scripts\init_workspace.py" 'C:\path\to\project' --name '项目名' --goal '项目目标' --apply
python "$HOME\.codex\skills\project-kickoff\scripts\doctor.py" 'C:\path\to\project' --json
```

## 验证

```powershell
python -m unittest discover -s "$HOME\.codex\skills\project-kickoff\scripts" -p 'test_*.py' -v
```

版本记录见 `CHANGELOG.md`。

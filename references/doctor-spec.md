# 只读索引巡检

doctor 不检查业务内容正确性，也不接管目录规范。仅在用户要求索引巡检或本次任务确实依赖的登记出现异常时使用；不因为进入项目、收工或准备归档自动运行。

```powershell
python "<skill>/scripts/doctor.py" "<项目目录>" --json
python "<skill>/scripts/doctor.py" "<项目目录>" --check-coverage --json
python "<skill>/scripts/doctor.py" "<项目目录>" --versioned-dir "报告" --json
```

只读取 `.project/MAP.md`。无索引仅报告未启用，不自动改用其他位置的同名文件，也不要求创建资料。根目录 AGENTS 提供工作指引，PROJECT 保存项目事实，doctor 不读取它们的内容。

| 字段 | 含义 | 影响退出码 |
|---|---|---|
| `map_missing_file` | 登记文件或目录不存在 | 1 |
| `map_invalid_path` | 绝对路径、越界路径或指向项目外部的链接 | 1 |
| `map_unregistered` | 显式启用 coverage 后发现的未登记文件，包括脚本 | 不影响 |
| `map_syntax_hint` | 登记使用了占位或通配模式，未作为有效路径 | 不影响 |
| `naming_hint` | 显式选定版本目录中未按版本格式命名的文件 | 不影响 |
| `version_gap` | 所选版本目录内按目录、名称、扩展名分组发现的跳号 | 不影响 |
| `notes` | 未使用索引等情况 | 不影响 |

退出码：0 为本次检查无失效/越界登记；1 为失效/越界登记；2 为目录、参数或读文件错误。0 不代表索引覆盖完整或项目全部健康。

默认只访问 MAP 与登记路径，不递归遍历项目。coverage 或版本目录检查才遍历，进入目录前裁剪 `.git`、`.codex`、`.agents`、`.project`、`node_modules`、`__pycache__`、`.venv`、`venv`；不跟随目录链接与 Windows junction，不读取系统杂项和 Office 锁文件。这不是完整依赖分析。跳过规则按准确目录名匹配，不吞掉 `node_modules备份` 或 `.github` 等路径。

使用行级登记识别，排除散文、表格、示例造成的幽灵登记。缺失路径不靠同名文件代替：同名不同目录可能是不同输入。默认检查不为寻找同名文件而全项目扫描，归因按需检索。

所有模式保持只读。允许在当前任务授权内修复相关索引；未授权的批量移动、改名或清理另行处理。版本跳号和命名只是建议，不据此强迫整改或发布。

项目脚本统一位于 `.project/scripts/`，coverage 检查按现有规则裁剪 `.project`；若要核对项目脚本的登记情况，需要在 MAP 中显式登记对应脚本路径，doctor 仍只做存在性检查，不执行业务脚本。

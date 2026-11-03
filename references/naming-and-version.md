# 产物版本管理（必用）

正式交付产物采用 `名称_v主.次_YYYYMMDD.ext`，如 `年度报告_v1.2_20261019.docx`。源代码、配置、外来原件和必须固定文件名的产物沿用项目规则。版本跳号可合理存在，不视为业务错误。

项目脚本统一存放在 `.project/scripts/`，版本模块固定复制为 `.project/scripts/_version.py`。项目级技能存放在 `.project/skill/<技能名>/`，自带脚本随技能保存。版本规则、工具入口及脚本/技能目录规则只写入 AGENTS；实际技能、调用条件与入口记录在 `.project/skill.md`，不在 PROJECT 重复。

```powershell
python .project/scripts/_version.py new --dir "报告" --name "年度报告" --ext .docx --today 20261019
python .project/scripts/_version.py latest --dir "报告" --name "年度报告"
python .project/scripts/_version.py versions --dir "报告" --name "年度报告"
python .project/scripts/_version.py register "报告/年度报告_v1.0_20261019.docx" --note "已生成并验证初稿"
```

- `new` 仅计算并打印路径，不创建文件、不记录变更。实际产物工具生成文件并验证格式和内容后再登记；不使用占位文件冒充完成。
- `latest` 按主版本、次版本、日期排序；同一逻辑名称含多种扩展名时停止，要求明确输入文件。复现、审计或用户指定版本时固定确切路径。
- `next_version` 次版本加一，次版本 99 后转入下一主版本的 0。结构大改是否升主版本由项目规则决定，工具不推断业务语义。
- `register` 需要已存在且符合版本格式的文件和已初始化的 PROGRESS。它只追加“重要变更记录”，保留当前进度原文及换行；不验证产物内部内容，不自动填写业务完成状态。
- 自动记录包含日期、产物路径、该产物版本和说明，并附带 HTML 事件标识。同一路径重复登记不重复追加；整理历史时保留标识。旧版无路径流水无法可靠对应文件，不推断或批量改写。
- 有旧 CHANGELOG 时登记停止，先由初始化器显式 `--migrate-changelog`。原文完整收纳到 PROGRESS 的历史围栏，原字节保留为 `CHANGELOG.md.history_<摘要>`；按 SHA-256 标记避免重复迁入，原事件标识继续去重。迁移同时备份并刷新版本模块，保留 PROJECT 业务事实。
- 已采用 PROGRESS 的旧项目用初始化器 `--refresh-version-tool` 预览并升级模块，不刷新 PROJECT 或当前进度。普通初始化保留已有定制模块；明确刷新时先备份。
- 不维护未发布/已发布分类。旧 `publish` CLI 被拒绝，库入口返回失败，均零写入。阶段成果、阻塞或下一步实质变化时，由 agent 根据证据更新当前进度并标用户时区日期。
- 可选全局参数 `--root "项目路径"` 放在子命令前；默认由已复制模块的位置推导项目根。CLI 日期取执行环境日期，跨时区时明确传 `--today YYYYMMDD`。`new` 校验真实日期，拒绝越界目录和含路径分隔符的逻辑名称。

库保留 `parse`、`latest`、`all_versions`、`next_version`、`rel`、`scan_all` 和进度登记辅助函数。`scan_all` 是版本文件发现工具，裁剪依赖、工具目录并不跟随目录链接。`append_progress` 为登记入口，旧库名 `append_changelog` 仅兼容写向 PROGRESS，不恢复旧活动日志。模块不要求所有业务脚本依赖它；改名、逻辑名或格式变化时核查调用者。

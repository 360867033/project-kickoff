"""Preview or create additive project metadata. No global configuration is touched."""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import datetime
from pathlib import Path

from workspace_common import local_path, select_metadata

AGENTS_BEGIN = "<!-- project-kickoff:begin -->"
AGENTS_END = "<!-- project-kickoff:end -->"


def build_documents(root: Path, meta: Path, name: str, goal: str) -> dict[str, str]:
    prefix = meta.relative_to(root).as_posix()
    versioning_note = (
        "必用：所有项目脚本统一存放在 `.project/scripts/`；技能自带脚本保留在各自技能目录内。正式交付产物采用 名称_v主.次_YYYYMMDD.ext，使用 `.project/scripts/_version.py` 管理版本，生成并验证后登记到 PROGRESS。代码、配置、外来原件和必须固定文件名的产物沿用项目规则。"
    )
    documents = {
        "AGENTS.md": f"""## 项目工作指引

- 开始项目任务时读取 `{prefix}/PROJECT.md` 和 `{prefix}/PROGRESS.md` 的“当前进度”，了解目标、完成条件及下一步；同一对话中已读且未变化时可复用，追溯时再读重要变更记录。
- 阶段成果、阻塞或下一步发生实质变化时更新 PROGRESS，带用户时区日期，写明实际完成范围、验证证据、未解决项与下一步；重要变更同页追加，不逐条回复记日志。
- 需要定位文件或核实依赖时，用 `rg --files`、`rg` 或目录工具定向检索实际文件，不将历史记录当作当前磁盘事实。
""",
        "PROJECT.md": f"""# {name}

## 目标

{goal or '待确认；不根据文件名猜测目标。'}

## 范围与完成条件

按用户请求及现有项目说明补充；未知事项标为待确认。

当前进度、阻塞、验证证据与下一步统一维护在 `PROGRESS.md`，不在此重复维护动态状态。

## 项目级技能

项目级技能统一存放在 `.project/skill/<技能名>/`，入口为 `.project/skill/<技能名>/SKILL.md`。技能自带的 scripts/、references/、assets/ 等资源保留在该技能目录内，新增技能时按需创建；初始化不创建空技能或复制 project-kickoff。

此位置是项目存放约定，不代表运行环境会自动发现或加载；使用时读取对应 SKILL.md，并在此记录实际运行环境的加载入口。已有技能迁移需在用户授权范围内核对引用与加载入口、备份并更新相关登记；个人或全局技能沿用原安装位置。

## 产物版本管理

{versioning_note}
""",
        "PROGRESS.md": "# 项目进度与重要变更\n\n## 当前进度\n\n- 更新时间：待首次实际更新时填写（用户时区）。\n- 当前状态：待根据实际任务核实。\n- 已完成与验证证据：待核实，不将计划视为完成。\n- 未解决项或阻塞：待核实。\n- 下一步：按用户目标确定。\n\n## 重要变更记录\n\n（暂无）\n",
    }
    return documents


def migrate_changelog(meta: Path, progress: bytes, legacy: bytes) -> tuple[bytes, Path]:
    """Append exact legacy prose once; preserve original bytes as a named history file."""
    digest = hashlib.sha256(legacy).hexdigest()
    marker = f"<!-- project-kickoff:legacy-changelog={digest} -->"
    text = progress.decode("utf-8-sig")
    body = legacy.decode("utf-8-sig")
    # A longer fence keeps legacy headings and even unclosed fences historical.
    fence = "`" * max(3, max((len(m) + 1 for m in re.findall(r"`+", body)), default=0))
    archive = meta / f"CHANGELOG.md.history_{digest[:16]}"
    if marker not in text:
        block = (
            "## 历史 CHANGELOG 原文（只读）\n\n"
            f"{marker}\n\n以下为原文；原有发布分类仅为历史，后续统一维护本文件。\n\n"
            + fence + "markdown\n" + body + ("" if body.endswith("\n") else "\n")
            + fence + "\n")
        progress += (b"\n" if progress.endswith(b"\n") else b"\n\n") + block.encode("utf-8")
    return progress, archive


def merge_agents(path: Path, body: str) -> bytes:
    """Replace only our marked block, preserving all surrounding bytes and newlines."""
    original = path.read_bytes() if path.exists() else b""
    original.decode("utf-8-sig")  # Reject unsupported encodings before any write.
    begin, end = AGENTS_BEGIN.encode(), AGENTS_END.encode()
    counts = (original.count(begin), original.count(end))
    newline = b"\r\n" if b"\r\n" in original else b"\n"
    block = (AGENTS_BEGIN + "\n" + body.rstrip() + "\n" + AGENTS_END).encode("utf-8")
    block = block.replace(b"\n", newline)
    if counts == (0, 0):
        separator = b"" if not original else newline if original.endswith(b"\n") else newline * 2
        return original + separator + block + newline
    if counts != (1, 1):
        raise ValueError("AGENTS.md 的 project-kickoff 区块标记缺失或重复，未写入任何文件")
    start, stop = original.index(begin), original.index(end)
    if stop < start:
        raise ValueError("AGENTS.md 的 project-kickoff 区块标记顺序错误，未写入任何文件")
    return original[:start] + block + original[stop + len(end):]


def write_file(path: Path, content: bytes, overwrite: bool) -> None:
    if path.exists():
        if path.read_bytes() == content:
            print(f"内容一致，保留：{path}")
            return
        if not overwrite:
            print(f"已有文件，保留：{path}")
            return
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S_%f")
        backup = path.with_name(f"{path.name}.bak_{stamp}")
        with backup.open("xb") as fh:
            fh.write(path.read_bytes())
        print(f"已备份：{backup}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    print(f"已写入：{path}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target")
    ap.add_argument("--name", default="")
    ap.add_argument("--goal", default="")
    ap.add_argument("--apply", action="store_true", help="写入；默认只预览")
    ap.add_argument("--force", action="store_true", help="备份后刷新 PROJECT/版本模块；AGENTS 仅更新托管区块")
    ap.add_argument("--refresh-version-tool", action="store_true", help="仅备份后刷新项目版本模块，保留 PROJECT 与 PROGRESS")
    ap.add_argument("--migrate-changelog", action="store_true", help="将旧 CHANGELOG 原文并入 PROGRESS，保留原件为只读历史")
    args = ap.parse_args()
    try:
        root = Path(args.target).resolve()
        if not root.is_dir():
            raise ValueError(f"目录不存在：{root}")
        override = root / "AGENTS.override.md"
        if override.is_file() and override.read_text(encoding="utf-8-sig").strip():
            raise ValueError("根目录 AGENTS.override.md 会遮蔽 AGENTS.md；请先明确项目指令入口，未写入任何文件")
        meta = select_metadata(root)
        if not meta.exists() and (root / "PROJECT.md").exists():
            raise ValueError("根目录已有项目说明；未创建并行资料，请按现有项目约定处理")
        documents = build_documents(root, meta, args.name or root.name, args.goal)
        agents_body = documents.pop("AGENTS.md")
        plan = {meta / k: v.encode("utf-8") for k, v in documents.items()}
        agents_path = root / "AGENTS.md"
        plan[agents_path] = agents_body.encode("utf-8")
        source = Path(__file__).resolve().parent.parent / "assets" / "_version.py"
        plan[meta / "scripts" / "_version.py"] = source.read_bytes()
        legacy_path = meta / "CHANGELOG.md"
        legacy = None
        archive = None
        if legacy_path.exists() or legacy_path.is_symlink():
            local_path(root, ".project/CHANGELOG.md")
            if legacy_path.is_symlink() or not legacy_path.is_file():
                raise ValueError("旧 CHANGELOG 不是可迁移的普通文件，未写入任何文件")
            if not args.migrate_changelog:
                raise ValueError("发现旧 CHANGELOG；请明确使用 --migrate-changelog 迁入 PROGRESS，未写入任何文件")
            progress_path = meta / "PROGRESS.md"
            local_path(root, ".project/PROGRESS.md")
            if progress_path.is_symlink() or (progress_path.exists() and not progress_path.is_file()):
                raise ValueError("PROGRESS 不是可更新的普通文件，未写入任何文件")
            legacy = legacy_path.read_bytes()
            existing = progress_path.read_bytes() if progress_path.exists() else plan[progress_path]
            plan[progress_path], archive = migrate_changelog(meta, existing, legacy)
            local_path(root, archive.relative_to(root).as_posix())
            if archive.is_symlink() or (archive.exists() and
                    (not archive.is_file() or archive.read_bytes() != legacy)):
                raise ValueError("历史原件位置冲突，未写入任何文件")
        for path in plan:
            local_path(root, path.relative_to(root).as_posix())
            if path.is_symlink() or (path.exists() and not path.is_file()):
                raise ValueError(f"目标不是可更新的普通文件：{path}")
        plan[agents_path] = merge_agents(agents_path, agents_body)
        for path, content in plan.items():
            overwrite = (path == agents_path or
                         (path.name == "PROGRESS.md" and legacy is not None) or
                         (path == meta / "scripts" / "_version.py" and
                          (args.force or args.refresh_version_tool or legacy is not None)) or
                         (path.name == "PROJECT.md" and args.force))
            if args.apply:
                write_file(path, content, overwrite)
            else:
                action = ("内容一致，保留" if path.exists() and path.read_bytes() == content else
                          "备份后更新托管区块，保留原文" if path == agents_path and path.exists() else
                          "备份后覆盖" if path.exists() and overwrite else "保留" if path.exists() else "新建")
                print(f"[预览] {action}：{path}")
        if legacy is not None:
            if args.apply:
                if not archive.exists():
                    with archive.open("xb") as fh:
                        fh.write(legacy)
                legacy_path.unlink()
                print(f"原 CHANGELOG 已保留为只读历史：{archive}")
            else:
                print(f"[预览] 将旧 CHANGELOG 原文并入 PROGRESS，并保留原件为：{archive}")
        if not args.apply:
            print("预览结束，未写入任何文件。执行时加 --apply。")
        return 0
    except (OSError, ValueError) as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

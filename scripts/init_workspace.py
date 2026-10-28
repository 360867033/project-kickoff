"""Preview or create additive project metadata. No global configuration is touched."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from workspace_common import iter_files, local_path, select_metadata

INIT_LIST_CAP = 100
AGENTS_BEGIN = "<!-- project-kickoff:begin -->"
AGENTS_END = "<!-- project-kickoff:end -->"


def build_documents(root: Path, meta: Path, name: str, goal: str) -> dict[str, str]:
    prefix = meta.relative_to(root).as_posix()
    versioning_note = (
        "必用：所有项目脚本统一存放在 `.project/scripts/`；技能自带脚本保留在各自技能目录内。正式交付产物采用 名称_v主.次_YYYYMMDD.ext，使用 `.project/scripts/_version.py` 管理版本，生成并验证后登记到 MAP 和 CHANGELOG；代码、配置、外来原件和必须固定文件名的产物沿用项目规则。"
    )
    # Include the instruction file that this plan will create, before writing MAP.
    files = sorted(set(iter_files(root)) | {"AGENTS.md"})
    groups: dict[str, list[str]] = {}
    for f in files[:INIT_LIST_CAP]:
        key = f.split("/", 1)[0] + "/" if "/" in f else "（项目根）"
        groups.setdefault(key, []).append(f)
    listing = "\n\n".join(f"### {k}\n\n" + "\n".join(f"- `{p}`" for p in v)
                             for k, v in groups.items()) or "（暂无文件。）"
    if len(files) > INIT_LIST_CAP:
        listing += f"\n\n仅列前 {INIT_LIST_CAP} 个，共 {len(files)} 个；这是部分快照，不代表完整覆盖。"
    return {
        "AGENTS.md": f"""## 项目工作指引

- 开始项目任务时读取 `{prefix}/PROJECT.md`，了解目标、范围、当前阶段与完成条件；同一对话中已读且未变化时可复用。
- 定位文件与上下游关系时读取 `{prefix}/MAP.md`；回顾变更时读取 `{prefix}/CHANGELOG.md`。
- 索引缺失或失效时定向检索实际文件，并同步本次改动涉及的关键登记。
""",
        "PROJECT.md": f"""# {name}

## 目标

{goal or '待确认；不根据文件名猜测目标。'}

## 范围与完成条件

按用户请求及现有项目说明补充；未知事项标为待确认。

## 当前阶段

待根据实际任务核实。

## 项目级技能

项目级技能统一存放在 `.project/skill/<技能名>/`，入口为 `.project/skill/<技能名>/SKILL.md`。技能自带的 scripts/、references/、assets/ 等资源保留在该技能目录内，新增技能时按需创建；初始化不创建空技能或复制 project-kickoff。

此位置是项目存放约定，不代表运行环境会自动发现或加载；使用时读取对应 SKILL.md，并在此记录实际运行环境的加载入口。已有技能迁移需在用户授权范围内核对引用与加载入口、备份并更新相关登记；个人或全局技能沿用原安装位置。

## 产物版本管理

{versioning_note}
""",
        "CHANGELOG.md": "# 项目记录\n\n按项目需要记录变更，不自动发布。\n\n## 未发布\n\n（暂无）\n",
        "MAP.md": f"""# MAP.md — {name} 的文件上下游索引

路径相对项目根。索引是辅助资料，磁盘现状需核实；允许按需检索未登记文件。
仅登记关键资产或目录，不要求全项目逐文件登记；初扫仅表示发现文件，不证明业务关系。

## 环节

待依据事实补充输入、脚本、输出及下游关系。

## 初扫文件清单（待归类）

{listing}
""",
    }


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
    ap.add_argument("--force-data", action="store_true", help="备份后重置 MAP/CHANGELOG")
    args = ap.parse_args()
    try:
        root = Path(args.target).resolve()
        if not root.is_dir():
            raise ValueError(f"目录不存在：{root}")
        override = root / "AGENTS.override.md"
        if override.is_file() and override.read_text(encoding="utf-8-sig").strip():
            raise ValueError("根目录 AGENTS.override.md 会遮蔽 AGENTS.md；请先明确项目指令入口，未写入任何文件")
        meta = select_metadata(root)
        if not meta.exists() and any((root / n).exists() for n in ("MAP.md", "PROJECT.md")):
            raise ValueError("根目录已有项目说明或索引；未创建并行资料，请按现有项目约定处理")
        documents = build_documents(root, meta, args.name or root.name, args.goal)
        agents_body = documents.pop("AGENTS.md")
        plan = {meta / k: v.encode("utf-8") for k, v in documents.items()}
        agents_path = root / "AGENTS.md"
        plan[agents_path] = agents_body.encode("utf-8")
        source = Path(__file__).resolve().parent.parent / "assets" / "_version.py"
        plan[meta / "scripts" / "_version.py"] = source.read_bytes()
        for path in plan:
            local_path(root, path.relative_to(root).as_posix())
            if path.is_symlink() or (path.exists() and not path.is_file()):
                raise ValueError(f"目标不是可更新的普通文件：{path}")
        plan[agents_path] = merge_agents(agents_path, agents_body)
        for path, content in plan.items():
            overwrite = (True if path == agents_path else args.force_data
                         if path.name in {"MAP.md", "CHANGELOG.md"} else args.force)
            if args.apply:
                write_file(path, content, overwrite)
            else:
                action = ("内容一致，保留" if path.exists() and path.read_bytes() == content else
                          "备份后更新托管区块，保留原文" if path == agents_path and path.exists() else
                          "备份后覆盖" if path.exists() and overwrite else "保留" if path.exists() else "新建")
                print(f"[预览] {action}：{path}")
        if not args.apply:
            print("预览结束，未写入任何文件。执行时加 --apply。")
        return 0
    except (OSError, ValueError) as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

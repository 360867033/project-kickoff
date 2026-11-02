"""Version-file library and CLI; new prints a path by default.
Copied into .project/scripts during initialization.
Use pinned paths for reproducible inputs. This module is not a universal naming rule.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path

__all__ = [
    "PATTERN", "META", "ROOT", "latest", "all_versions",
    "next_version", "parse", "rel", "scan_all",
    "append_progress", "append_changelog", "publish_changelog",
]

# 名称_v主.次_YYYYMMDD.扩展名
PATTERN = re.compile(
    r'^(?P<name>.+)_v(?P<major>\d+)\.(?P<minor>\d+)_(?P<date>\d{8})(?P<ext>\.[^.]+)$'
)

# META is the chosen metadata directory; ROOT is the project.
META = Path(__file__).resolve().parent.parent
ROOT = META.parent


def parse(filename: str) -> dict | None:
    """解析单个文件名，合规返回 dict，不合规返回 None。"""
    m = PATTERN.match(filename)
    if not m:
        return None
    return {
        "name": m["name"],
        "major": int(m["major"]),
        "minor": int(m["minor"]),
        "date": m["date"],
        "ext": m["ext"],
        "version": (int(m["major"]), int(m["minor"])),
    }


def _collect(rel_dir: str, name: str) -> list[tuple, Path]:
    """收集某目录下指定逻辑名称的全部合规版本，按(主,次,日期)升序。"""
    base = _local(rel_dir)
    if not base.is_dir():
        return []
    out: list[tuple, Path] = []
    for p in base.iterdir():
        if not p.is_file():
            continue
        info = parse(p.name)
        if info and info["name"] == name:
            out.append((info["version"] + (info["date"],), p))
    if len({p.suffix.lower() for _, p in out}) > 1:
        raise ValueError("同一逻辑名含多种格式，请明确指定输入文件，避免自动选择错误格式")
    return sorted(out, key=lambda x: x[0])


def latest(rel_dir: str, name: str) -> Path | None:
    """取目录下某逻辑名称的最新版本文件。无则返回 None。"""
    found = _collect(rel_dir, name)
    return found[-1][1] if found else None


def all_versions(rel_dir: str, name: str) -> list[Path]:
    """取全部历史版本，按版本号升序。用于挑上一版做对比。"""
    return [p for _, p in _collect(rel_dir, name)]


def next_version(rel_dir: str, name: str, ext: str, today: str) -> Path:
    """算出下一个版本的目标路径（不创建文件）。

    版本语义：改内容/改结构 → 次版本号 +1；推翻重来 → 主版本号 +1（次归 0）。
    """
    from datetime import datetime
    datetime.strptime(today, "%Y%m%d")
    if not name or any(c in name for c in '/\\:*?"<>|') or Path(name).name != name:
        raise ValueError("逻辑名称须为单个有效文件名")
    if not re.fullmatch(r"\.?[A-Za-z0-9]+", ext):
        raise ValueError("扩展名须为单个扩展名，如 .xlsx")
    _local(rel_dir)
    cur = latest(rel_dir, name)
    major, minor = 1, 0
    if cur is not None:
        info = parse(cur.name)
        major, minor = info["major"], info["minor"]
        major, minor = (major, minor + 1) if minor < 99 else (major + 1, 0)
    if not ext.startswith("."):
        ext = "." + ext
    return _local(rel_dir) / f"{name}_v{major}.{minor}_{today}{ext}"


def rel(p: Path) -> str:
    """绝对路径 → 相对项目根的 POSIX 风格路径，供写进项目记录。"""
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def _local(relative: str) -> Path:
    p = (ROOT / relative).resolve()
    if not p.is_relative_to(ROOT.resolve()):
        raise ValueError(f"路径超出项目范围：{relative}")
    return p


def scan_all(skip_dirs: tuple[str, ...] = ()) -> list[tuple[str, dict | None]]:
    """Prune tool/dependency directories rather than traversing them first."""
    skip = {".project", ".git", ".codex", ".agents",
            "node_modules", "__pycache__", ".venv", "venv"}
    out = []
    for current, dirs, files in os.walk(ROOT, followlinks=False):
        here = Path(current)
        dirs[:] = sorted(d for d in dirs if d not in skip
                         and not (here / d).is_symlink()
                         and not (hasattr(Path, "is_junction") and (here / d).is_junction()))
        for name in sorted(files):
            p = here / name
            if p.is_symlink():
                continue
            r = p.relative_to(ROOT).as_posix()
            if any(r == q or r.startswith(q.rstrip("/") + "/") for q in skip_dirs):
                continue
            out.append((r, parse(name)))
    return out


# ---------------------------------------------------------------- CLI 支撑 --

def _section_bounds(text: str, title: str) -> tuple[int, int, int] | None:
    """Locate an H2 section, keeping subheadings, comments and fenced text inside."""
    offset = 0
    start = None
    fence = None
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        marker = re.match(r"^(`{3,}|~{3,})", stripped)
        if marker:
            mark = marker[1]
            if fence is None:
                fence = mark
            elif mark[0] == fence[0] and len(mark) >= len(fence):
                fence = None
        elif fence is None and re.match(r"^#{1,2}(?:\s|$)", line):
            if start is not None:
                return (*start, offset)
            if stripped == f"## {title}":
                start = (offset, offset + len(line))
        offset += len(line)
    return (*start, len(text)) if start is not None else None


def append_progress(meta: Path, ver: str, today_iso: str, note: str,
                     artifact_path: str) -> None:
    """Record a file event once without changing the current-progress section."""
    if _metadata_file(meta, "CHANGELOG.md").exists():
        raise ValueError("发现旧 CHANGELOG；先显式迁移到 PROGRESS，再登记")
    path = _metadata_file(meta, "PROGRESS.md", required=True)
    # Preserve current-progress bytes, including BOM and CRLF, outside the edited section.
    text = path.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    identity = os.path.normcase(_local(artifact_path).relative_to(ROOT.resolve()).as_posix())
    key = hashlib.sha256(identity.replace("\\", "/").encode("utf-8")).hexdigest()
    marker = f"<!-- project-kickoff:artifact={key} -->"
    if marker in text:
        return
    note = " ".join(note.splitlines()) or "（未填说明）"
    new_line = f"- {today_iso} | 产物新增 | `{artifact_path}` | v{ver} | {note} {marker}"
    section = _section_bounds(text, "重要变更记录")
    if section:
        _, begin, end = section
        body = text[begin:end].strip("\r\n")
        if body.strip() == "（暂无）":
            body = ""
        text = (text[:begin] + newline + new_line + newline
                + (newline + body + newline if body else "")
                + (newline if text[end:] else "") + text[end:])
    else:
        text = text + newline + "## 重要变更记录" + newline * 2 + new_line + newline
    path.write_bytes(text.encode("utf-8"))


def publish_changelog(meta: Path, today_iso: str, note: str = "") -> int:
    """Retired compatibility entrypoint: reject without reading or writing project data."""
    print("[错误] publish 已移除；请直接维护 PROGRESS 的当前进度与重要变更记录。", file=sys.stderr)
    return 1


def _metadata_file(meta: Path, filename: str, required: bool = False) -> Path:
    raw = meta / filename
    _local(raw.relative_to(ROOT).as_posix())
    if raw.is_symlink() or (raw.exists() and not raw.is_file()):
        raise ValueError(f"辅助资料不是普通文件：{raw}")
    if required and not raw.is_file():
        raise ValueError(f"缺少辅助资料：{raw}；请先初始化或迁移旧 CHANGELOG")
    return raw


def append_changelog(meta: Path, ver: str, today_iso: str, note: str,
                     artifact_path: str) -> None:
    """Compatibility alias: new records go only to PROGRESS."""
    append_progress(meta, ver, today_iso, note, artifact_path)


def _register_existing(meta: Path, path: Path, info: dict, note: str) -> None:
    # Validate the single active record before any mutation.
    legacy = _metadata_file(meta, "CHANGELOG.md")
    if legacy.exists():
        raise ValueError("发现旧 CHANGELOG；先用初始化器 --migrate-changelog 迁入 PROGRESS，再登记")
    _metadata_file(meta, "PROGRESS.md", required=True)
    date = info["date"]
    append_progress(meta, f'{info["major"]}.{info["minor"]}',
                    f"{date[:4]}-{date[4:6]}-{date[6:]}", note, rel(path))


def _self_check() -> int:
    """自检：打印项目根与当前识别到的全部合规版本文件。"""
    print(f"ROOT = {ROOT}")
    print(f"META   = {META}")
    rows = [(r, i) for r, i in scan_all((".project",)) if i]
    print(f"识别到 {len(rows)} 个合规版本文件")
    for r, i in rows:
        print(f"  v{i['major']}.{i['minor']}  {i['date']}  {r}")
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys
    from datetime import date as _date

    def _err(msg: str) -> None:
        print(msg, file=sys.stderr)

    global ROOT

    ap = argparse.ArgumentParser(
        prog="_version.py",
        description="版本解析模块的 CLI：自检 / 新建产物版本 / 查询版本",
    )
    ap.add_argument("--root", default=None, help="项目目录，默认由已复制模块位置确定")
    sub = ap.add_subparsers(dest="cmd")

    p_new = sub.add_parser("new", help="计算下一版本路径；默认不落盘")
    p_new.add_argument("--dir", required=True, help="相对项目根的目录")
    p_new.add_argument("--name", required=True, help="逻辑名称（不含版本号）")
    p_new.add_argument("--ext", default="", help="扩展名，如 .xlsx；缺省继承最新版")
    p_new.add_argument("--today", default="", help="日期 YYYYMMDD，默认今天")

    p_lat = sub.add_parser("latest", help="打印最新版路径")
    p_lat.add_argument("--dir", required=True)
    p_lat.add_argument("--name", required=True)

    p_ver = sub.add_parser("versions", help="打印全部历史版本")
    p_ver.add_argument("--dir", required=True)
    p_ver.add_argument("--name", required=True)

    p_reg = sub.add_parser("register", help="登记已由实际文档工具生成的版本文件")
    p_reg.add_argument("path", help="项目根相对路径")
    p_reg.add_argument("--note", default="")
    args = ap.parse_args(argv)

    if args.root:
        t = Path(args.root).resolve()
        if not t.is_dir():
            _err(f"[错误] 目录不存在：{t}")
            return 1
        ROOT = t

    meta = _local(".project")

    if args.cmd == "register":
        path = _local(args.path)
        info = parse(path.name)
        if not path.is_file() or not info:
            raise ValueError("register 需要已存在、符合所选版本命名的文件")
        _register_existing(meta, path, info, args.note)
        print(f"已登记：{rel(path)}")
        return 0

    if args.cmd is None:
        return _self_check()

    if args.cmd == "latest":
        p = latest(args.dir, args.name)
        if not p:
            _err(f"[未找到] {args.dir} 下名为「{args.name}」的版本文件")
            return 2
        print(p)
        return 0

    if args.cmd == "versions":
        hist = all_versions(args.dir, args.name)
        if not hist:
            _err(f"[未找到] {args.dir} 下名为「{args.name}」的版本文件")
            return 2
        for h in hist:
            print(h)
        return 0

    # ---- new ----
    today = args.today or _date.today().strftime("%Y%m%d")
    if not args.ext:
        cur = latest(args.dir, args.name)
        if cur:
            args.ext = parse(cur.name)["ext"]
        else:
            _err("[错误] 首次生成需用 --ext 指定扩展名")
            return 1

    nxt = next_version(args.dir, args.name, args.ext, today)
    print(nxt)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        raise SystemExit(1)

"""Optional version-file library and CLI; new prints a path by default.
Copied into .project/scripts when opted in.
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
    "append_changelog", "append_map", "publish_changelog",
    "collect_registered",
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
    """绝对路径 → 相对项目根的 POSIX 风格路径，供写进 MAP.md。"""
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

def collect_registered(map_path: Path) -> tuple[list[str], list[str]]:
    """Shared MAP syntax for doctor and the self-contained copied version tool."""
    paths, hints = [], []
    fence = None
    in_init = False
    field_indent = None
    for line in map_path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        marker = re.match(r"^(`{3,}|~{3,})", stripped)
        if marker:
            mark = marker[1]
            if fence is None:
                fence = mark
            elif mark[0] == fence[0] and len(mark) >= len(fence):
                fence = None
            field_indent = None
            continue
        if fence:
            continue
        if stripped.startswith("## ") or stripped == "##":
            in_init = "初扫文件清单" in stripped
            field_indent = None
            continue
        if not stripped or stripped.startswith("#"):
            field_indent = None
            continue
        bullet = re.match(r"^(\s*)[-*]\s+", line)
        indent = len(bullet[1]) if bullet else 0
        field = bool(re.match(r"^\s*[-*]\s*[^：:\n]{1,12}[:：]", line)
                     or re.match(r"^\s*[-*]\s*【登记】", line))
        child = bullet and field_indent is not None and indent > field_indent
        if not bullet or not (in_init or field or child):
            field_indent = None
            continue
        if field:
            field_indent = indent
        for entry in re.findall(r"`([^`]+)`", line):
            entry = entry.strip()
            if not entry or entry == ".project" or entry.startswith(".project/"):
                continue
            (hints if any(c in entry for c in "<>*?[") else paths).append(entry)
    return paths, hints


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


def append_changelog(meta: Path, ver: str, today_iso: str, note: str,
                     artifact_path: str) -> None:
    """Record a file event once; its identity lives in CHANGELOG, independently of MAP."""
    path = meta / "CHANGELOG.md"
    text = path.read_text(encoding="utf-8-sig") if path.exists() else "# 项目记录\n"
    identity = os.path.normcase(_local(artifact_path).relative_to(ROOT.resolve()).as_posix())
    key = hashlib.sha256(identity.replace("\\", "/").encode("utf-8")).hexdigest()
    marker = f"<!-- project-kickoff:artifact={key} -->"
    if marker in text:
        return
    note = " ".join(note.splitlines()) or "（未填说明）"
    new_line = f"- {today_iso} | 产物新增 | `{artifact_path}` | v{ver} | {note} {marker}"
    section = _section_bounds(text, "未发布")
    if section:
        _, begin, end = section
        body = text[begin:end].strip("\n")
        if body.strip() == "（暂无）":
            body = ""
        text = (text[:begin] + "\n" + new_line + "\n"
                + ("\n" + body + "\n" if body else "")
                + ("\n" if text[end:] else "") + text[end:])
    else:
        text = text.rstrip("\n") + "\n\n## 未发布\n\n" + new_line + "\n"
    path.write_text(text, encoding="utf-8")


def append_map(meta: Path, rel_path: str) -> None:
    """Register only paths not already indexed as files or covered by a directory."""
    path = meta / "MAP.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8-sig")
    target = _local(rel_path)
    entries, _ = collect_registered(path)
    for entry in entries:
        if Path(entry).is_absolute() or entry.startswith(("/", "\\")):
            continue
        try:
            registered = _local(entry)
        except (OSError, ValueError):
            continue
        if target == registered or (registered.is_dir() and target.is_relative_to(registered)):
            return
    line = f"- 产物登记：`{rel_path}`\n"
    section = _section_bounds(text, "产物登记")
    if section:
        _, _, end = section
        text = text[:end].rstrip("\n") + "\n" + line + ("\n" if text[end:] else "") + text[end:]
    else:
        text = text.rstrip("\n") + "\n\n## 产物登记\n\n" + line
    path.write_text(text, encoding="utf-8")


def publish_changelog(meta: Path, today_iso: str, note: str = "") -> int:
    """Move the complete unpublished body into a dated batch, preserving project prose."""
    from datetime import date

    date.fromisoformat(today_iso)
    path = meta / "CHANGELOG.md"
    if not path.exists():
        print(f"[错误] 未找到 {path}", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8-sig")
    section = _section_bounds(text, "未发布")
    if not section:
        print("未发现「未发布」段，无需发布。")
        return 0
    _, begin, end = section
    body = text[begin:end].strip("\n")
    if body.strip() in ("", "（暂无）"):
        print("「未发布」段为空，无需发布。")
        return 0
    block = f"### {today_iso}\n\n"
    if note:
        block += note + "\n\n"
    block += body + "\n\n"
    out = text[:begin] + "\n（暂无）\n\n" + text[end:]
    published = _section_bounds(out, "已发布")
    if published:
        _, pub_begin, _ = published
        out = out[:pub_begin] + "\n" + block + out[pub_begin:]
    else:
        out = out.rstrip("\n") + "\n\n## 已发布\n\n" + block
    path.write_text(out, encoding="utf-8")
    print(f"已按 {today_iso} 整理项目记录：完整正文移入「已发布」段")
    return 0


def _register_existing(meta: Path, path: Path, info: dict, note: str) -> None:
    for filename in ("MAP.md", "CHANGELOG.md"):
        destination = _local((meta / filename).relative_to(ROOT).as_posix())
        if not destination.is_file():
            raise ValueError(f"缺少辅助资料：{destination}")
    date = info["date"]
    append_changelog(meta, f'{info["major"]}.{info["minor"]}',
                     f"{date[:4]}-{date[4:6]}-{date[6:]}", note, rel(path))
    append_map(meta, rel(path))


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

    p_pub = sub.add_parser("publish", help="把「未发布」段全部条目移入「已发布」段")
    p_pub.add_argument("--note", default="", help="发布说明（写入发布块）")
    p_pub.add_argument("--today", default="", help="日期 YYYYMMDD，默认今天")

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

    if args.cmd == "publish":
        _local(".project/CHANGELOG.md")
        today = args.today or _date.today().strftime("%Y%m%d")
        today_iso = f"{today[:4]}-{today[4:6]}-{today[6:]}"
        return publish_changelog(meta, today_iso, args.note)

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

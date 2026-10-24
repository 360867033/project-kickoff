"""Read-only MAP check; coverage and scoped version hints are opt-in."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from workspace_common import iter_files, local_path, select_metadata

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "assets"))
import _version as V

collect_registered = V.collect_registered


def check(root: Path, meta: Path, coverage: bool = False,
          versioned_dirs: list[str] | None = None) -> dict:
    findings = {k: [] for k in (
        "map_missing_file", "map_invalid_path", "map_unregistered",
        "map_syntax_hint", "naming_hint", "version_gap", "notes")}
    mp = meta / "MAP.md"
    if not mp.is_file():
        findings["notes"].append("未发现 MAP；本项目未采用索引时无需初始化。")
        return findings
    entries, syntax = collect_registered(mp)
    findings["map_syntax_hint"] = sorted(set(syntax))
    registered_dirs, registered = [], set()
    for r in sorted(set(entries)):
        try:
            if Path(r).is_absolute() or r.startswith(("/", "\\")):
                raise ValueError(f"须使用项目根相对路径：{r}")
            p = local_path(root, r)
        except (ValueError, OSError) as exc:
            findings["map_invalid_path"].append(str(exc))
            continue
        if p.is_dir():
            registered_dirs.append(p)
        if not p.exists():
            findings["map_missing_file"].append(r)
        registered.add(p)
    # Default validity checking does not walk the project.
    scopes = [local_path(root, d) for d in (versioned_dirs or [])]
    files = list(iter_files(root)) if coverage or scopes else []
    if coverage:
        for r in files:
            p = local_path(root, r)
            if p == mp or p in registered:
                continue
            if not any(p.is_relative_to(d) for d in registered_dirs):
                findings["map_unregistered"].append(r)
    versions = {}
    for r in files:
        p = local_path(root, r)
        if not any(p.is_relative_to(d) for d in scopes):
            continue
        info = V.parse(p.name)
        if not info:
            findings["naming_hint"].append(r)
        else:
            key = (p.parent.as_posix(), info["name"], info["ext"])
            versions.setdefault(key, set()).add(info["version"])
    for (directory, name, ext), vers in versions.items():
        ordered = sorted(vers)
        for a, b in zip(ordered, ordered[1:]):
            if b != (a[0], a[1] + 1) and not (a[1] == 99 and b == (a[0] + 1, 0)):
                findings["version_gap"].append(
                    f"{directory}/{name}{ext}: {a} -> {b}（仅提示，不证明缺失）")
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check-coverage", action="store_true", help="遍历项目检查未登记文件，仅作提示")
    ap.add_argument("--versioned-dir", action="append", default=[], help="仅对选定相对目录提示版本命名")
    args = ap.parse_args()
    try:
        root = Path(args.target).resolve()
        if not root.is_dir():
            raise ValueError(f"目录不存在：{root}")
        meta = select_metadata(root)
        f = check(root, meta, args.check_coverage, args.versioned_dir)
    except (OSError, ValueError) as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(f, ensure_ascii=False, indent=2))
    else:
        print(f"索引巡检：{root}")
        for key, items in f.items():
            if items:
                print(f"{key}（{len(items)}）")
                for item in items[:30]:
                    print(f"  - {item}")
        if not any(f.values()):
            print("本次检查范围内未发现异常。")
        print("登记遗漏、命名与版本跳号仅作提示；不会修改任何文件。")
    return 1 if f["map_missing_file"] or f["map_invalid_path"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

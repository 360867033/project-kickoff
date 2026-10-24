"""Project metadata selection and pruned, project-local file discovery."""
from __future__ import annotations

import os
from pathlib import Path

META_DIR = ".project"
SKIP_DIRS = {".git", ".codex", ".agents", "node_modules", "__pycache__", ".venv", "venv", META_DIR}
JUNK_NAMES = {"desktop.ini", "thumbs.db", ".ds_store"}


def local_path(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise ValueError(f"路径超出项目范围：{relative}")
    return candidate


def select_metadata(root: Path) -> Path:
    selected = root / META_DIR
    local_path(root, META_DIR)
    if selected.exists() and not selected.is_dir():
        raise ValueError(f"辅助目录位置已被文件占用：{selected}")
    return selected


def iter_files(root: Path):
    """Prune dependencies and tool metadata before descent; never follow links/junctions."""
    for current, dirs, files in os.walk(root, followlinks=False):
        here = Path(current)
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS
                         and not (here / d).is_symlink()
                         and not (hasattr(Path, "is_junction") and (here / d).is_junction()))
        for name in sorted(files):
            p = here / name
            if name.lower() in JUNK_NAMES or name.startswith("~$") or p.is_symlink():
                continue
            yield p.relative_to(root).as_posix()

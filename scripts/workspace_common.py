"""Fixed project metadata selection with project-local path validation."""
from __future__ import annotations

from pathlib import Path

META_DIR = ".project"


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


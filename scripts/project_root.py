from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT_MARKERS = (
    "Client",
    "Server",
    "common",
    "packaging",
    "scripts",
    "requirements.txt",
)


def looks_like_project_root(path: Path) -> bool:
    return path.is_dir() and all((path / marker).exists() for marker in PROJECT_ROOT_MARKERS)


def _candidate_from_env(name: str) -> Path | None:
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    return Path(value).expanduser()


def resolve_project_root(script_file: str) -> Path:
    for candidate in (
        _candidate_from_env("TCPTRANSGUI_PROJECT_ROOT"),
        _candidate_from_env("PWD"),
        Path.cwd(),
        Path(script_file).resolve().parents[1],
    ):
        if candidate is not None and looks_like_project_root(candidate):
            return candidate
    return Path(script_file).resolve().parents[1]

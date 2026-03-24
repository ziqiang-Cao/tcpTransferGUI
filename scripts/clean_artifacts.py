from __future__ import annotations

import argparse
import shutil

from project_root import resolve_project_root


PROJECT_ROOT = resolve_project_root(__file__)
REMOVE_DIRS = {
    "build",
    "dist",
    "release",
    "client_data_test_smoke",
    ".pytest_cache",
}


def remove_generated_artifacts(keep_release=False):
    for path in PROJECT_ROOT.rglob("*"):
        if path.name == "__pycache__" and path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
    for pattern in ("*.pyc", "*.pyo"):
        for path in PROJECT_ROOT.rglob(pattern):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
    for name in REMOVE_DIRS:
        if keep_release and name == "release":
            continue
        target = PROJECT_ROOT / name
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description="Remove generated build artifacts.")
    parser.add_argument("--keep-release", action="store_true", help="保留 release 目录，只清理中间产物")
    args = parser.parse_args()
    remove_generated_artifacts(keep_release=args.keep_release)
    print("Generated build artifacts removed.")


if __name__ == "__main__":
    main()

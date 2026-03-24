from __future__ import annotations

import platform
import subprocess

from project_root import resolve_project_root


PROJECT_ROOT = resolve_project_root(__file__)


def run(command):
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def main():
    system = platform.system().lower()
    if system == "windows":
        script = PROJECT_ROOT / "scripts" / "build_windows.bat"
        run(["cmd", "/c", str(script)])
        return
    if system == "linux":
        script = PROJECT_ROOT / "scripts" / "build_ubuntu.sh"
        run(["bash", str(script)])
        return
    raise SystemExit(f"Unsupported build host: {platform.system()}")


if __name__ == "__main__":
    main()

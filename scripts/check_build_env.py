from __future__ import annotations

import platform
import shutil
import sys


def main() -> int:
    major, minor = sys.version_info[:2]
    machine = platform.machine().lower()

    if major != 3 or minor < 10:
        print(
            "[tcpTransGUI] 当前 Python 版本过低。"
            " 请使用 Python 3.10-3.12 进行构建。"
        )
        return 1

    if minor >= 13:
        print(
            "[tcpTransGUI] 当前检测到 Python "
            f"{major}.{minor}，PyQt5 在该版本上通常没有可直接使用的预编译 wheel，"
            " 尤其在 arm64/aarch64 平台会退回源码构建并要求 qmake。"
        )
        print(
            "[tcpTransGUI] 建议改用 Python 3.12 重新创建虚拟环境后再执行打包。"
        )
        print(
            "[tcpTransGUI] 例如："
            "\n  conda create -n tcptransgui-py312 python=3.12 -y"
            "\n  conda activate tcptransgui-py312"
            "\n  python -m pip install -r requirements.txt pyinstaller"
        )
        return 1

    if machine in {"aarch64", "arm64"} and shutil.which("qmake") is None:
        print(
            "[tcpTransGUI] 当前为 ARM 平台，未检测到 qmake。"
            " 如果 pip 退回源码编译 PyQt5，将会失败。"
        )
        print(
            "[tcpTransGUI] 更推荐直接使用 conda-forge 预编译包，"
            " 例如 `conda env create -f environment.arm64.yml`。"
        )
        print(
            "[tcpTransGUI] 若仍需源码构建，请先安装 Qt 开发工具，例如："
            "\n  sudo apt install qtbase5-dev qtchooser qt5-qmake qtbase5-dev-tools"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

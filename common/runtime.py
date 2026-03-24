import os
import sys
from pathlib import Path


APP_NAME = "TCPTransGUI"


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def bundle_root():
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return project_root()


def project_root():
    return Path(__file__).resolve().parents[1]


def import_root():
    return Path(sys.executable).resolve().parent if is_frozen() else project_root()


def _nearest_existing_dir(path):
    current = Path(path).resolve()
    while not current.exists() and current != current.parent:
        current = current.parent
    return current


def _is_dir_writable(path):
    existing = _nearest_existing_dir(path)
    return os.access(existing, os.W_OK | os.X_OK)


def _user_data_home():
    override = os.environ.get("TCPTRANSGUI_DATA_HOME", "").strip()
    if override:
        return Path(override).expanduser()
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    xdg_data_home = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg_data_home:
        return Path(xdg_data_home).expanduser() / APP_NAME
    return Path.home() / ".local" / "share" / APP_NAME


def data_root(name):
    base_dir = import_root()
    if _is_dir_writable(base_dir):
        return base_dir / name
    return _user_data_home() / name


def resource_path(*parts):
    return bundle_root().joinpath(*parts)

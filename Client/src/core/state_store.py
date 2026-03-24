import json
from datetime import datetime
from pathlib import Path
from threading import RLock

from Client.src.core.client import parse_server_address
from common.defaults import DEFAULT_LOCAL_SERVER


DEFAULT_SETTINGS = {
    "last_server": DEFAULT_LOCAL_SERVER,
    "last_username": "",
    "thread_count": 4,
}


class ClientStateStore:
    def __init__(self, data_root):
        self.data_root = Path(data_root)
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_root / "state.json"
        self._lock = RLock()
        self._state = self._load()

    def _load(self):
        if self.state_file.exists():
            try:
                with self.state_file.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
            except (OSError, json.JSONDecodeError):
                backup_path = self.state_file.with_suffix(".broken.json")
                try:
                    self.state_file.replace(backup_path)
                except OSError:
                    pass
                return {"settings": {}, "profiles": {}, "trusted_servers": {}}
            if not isinstance(data, dict):
                return {"settings": {}, "profiles": {}, "trusted_servers": {}}
            data.setdefault("settings", {})
            data.setdefault("profiles", {})
            data.setdefault("trusted_servers", {})
            return data
        return {"settings": {}, "profiles": {}, "trusted_servers": {}}

    def _save(self):
        temp_path = self.state_file.with_suffix(".json.tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(self._state, handle, ensure_ascii=False, indent=2)
        temp_path.replace(self.state_file)

    @staticmethod
    def canonical_server(server_text):
        try:
            host, port = parse_server_address(server_text)
            return f"tcp://{host}:{port}"
        except Exception:
            return server_text.strip().lower()

    def _profile_key(self, server_text, username):
        server = self.canonical_server(server_text)
        return f"{server}::{username.strip().lower()}"

    def load_settings(self):
        with self._lock:
            settings = dict(DEFAULT_SETTINGS)
            settings.update(self._state.get("settings", {}))
            if settings.get("last_server", "").strip() == "tcp://127.0.0.1:445":
                settings["last_server"] = DEFAULT_LOCAL_SERVER
            settings["last_username"] = ""
            return settings

    def save_settings(self, **updates):
        with self._lock:
            settings = self.load_settings()
            for key, value in updates.items():
                if value is not None:
                    settings[key] = value
            self._state["settings"] = settings
            self._save()

    def load_tasks(self, server_text, username):
        with self._lock:
            profile = self._state["profiles"].get(self._profile_key(server_text, username), {})
            return [dict(task) for task in profile.get("tasks", [])]

    def save_tasks(self, server_text, username, tasks):
        with self._lock:
            key = self._profile_key(server_text, username)
            tasks = [dict(task) for task in tasks]
            if tasks:
                self._state["profiles"][key] = {
                    "server": self.canonical_server(server_text),
                    "username": username,
                    "updated_at": datetime.now().isoformat(timespec="seconds"),
                    "tasks": tasks,
                }
            else:
                self._state["profiles"].pop(key, None)
            self._save()

    def load_server_fingerprint(self, server_text):
        with self._lock:
            return self._state.get("trusted_servers", {}).get(self.canonical_server(server_text), "")

    def save_server_fingerprint(self, server_text, fingerprint):
        with self._lock:
            trusted = dict(self._state.get("trusted_servers", {}))
            trusted[self.canonical_server(server_text)] = fingerprint
            self._state["trusted_servers"] = trusted
            self._save()

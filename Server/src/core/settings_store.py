import json
from pathlib import Path
from threading import RLock

from common.defaults import (
    DEFAULT_SERVER_HOST,
    DEFAULT_SERVER_PORT,
    LEGACY_PRIVILEGED_DEFAULT_PORT,
)


DEFAULT_SERVER_SETTINGS = {
    "host": DEFAULT_SERVER_HOST,
    "port": DEFAULT_SERVER_PORT,
    "auto_start_service": False,
}


class ServerSettingsStore:
    def __init__(self, settings_file):
        self.settings_file = Path(settings_file)
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._settings = self._load()
        if self.settings_file.exists():
            self._save()

    @staticmethod
    def _normalize_settings(settings):
        normalized = dict(settings)
        host = (normalized.get("host") or DEFAULT_SERVER_HOST).strip() or DEFAULT_SERVER_HOST
        port = int(normalized.get("port", DEFAULT_SERVER_PORT))
        if host == DEFAULT_SERVER_HOST and port == LEGACY_PRIVILEGED_DEFAULT_PORT:
            port = DEFAULT_SERVER_PORT
        normalized["host"] = host
        normalized["port"] = port
        return normalized

    def _load(self):
        if self.settings_file.exists():
            with self.settings_file.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            settings = dict(DEFAULT_SERVER_SETTINGS)
            settings.update(data)
            return self._normalize_settings(settings)
        return self._normalize_settings(DEFAULT_SERVER_SETTINGS)

    def _save(self):
        temp_path = self.settings_file.with_suffix(".json.tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(self._settings, handle, ensure_ascii=False, indent=2)
        temp_path.replace(self.settings_file)

    def load(self):
        with self._lock:
            return dict(self._settings)

    def save(self, **updates):
        with self._lock:
            for key, value in updates.items():
                if value is not None:
                    self._settings[key] = value
            self._save()

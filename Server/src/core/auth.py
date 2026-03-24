import hashlib
import json
import shutil
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path


class UserStore:
    def __init__(self, users_file, storage_root):
        self.users_file = Path(users_file)
        self.storage_root = Path(storage_root)
        self.lock = threading.RLock()
        self.users_file.parent.mkdir(parents=True, exist_ok=True)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self._data = self._load()
        self._ensure_default_admin()

    def _load(self):
        if self.users_file.exists():
            with self.users_file.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            data.setdefault("users", [])
            return data
        return {"users": []}

    def _save(self):
        with self.users_file.open("w", encoding="utf-8") as handle:
            json.dump(self._data, handle, ensure_ascii=False, indent=2)

    @staticmethod
    def _utc_now():
        return datetime.now(timezone.utc)

    @staticmethod
    def _hash_password(username, password):
        return hashlib.sha256(f"{username}:{password}".encode("utf-8")).hexdigest()

    def _ensure_default_admin(self):
        with self.lock:
            if any(user.get("is_primary_admin") for user in self._data["users"]):
                return
            legacy_admin = self._find_user("admin")
            if legacy_admin:
                legacy_admin["is_primary_admin"] = True
                legacy_admin.setdefault("password_seed_username", legacy_admin["username"])
                self._save()
                return
        self.create_user("admin", "admin123", role="admin", is_primary_admin=True)

    def _find_user(self, username):
        for user in self._data["users"]:
            if user["username"] == username:
                return user
        return None

    def _is_expired(self, user, now=None):
        expires_at = user.get("expires_at")
        if not expires_at:
            return False
        now = now or self._utc_now()
        try:
            expires_dt = datetime.fromisoformat(expires_at)
        except ValueError:
            return False
        if expires_dt.tzinfo is None:
            expires_dt = expires_dt.replace(tzinfo=timezone.utc)
        return expires_dt <= now

    @staticmethod
    def _user_payload(user):
        expires_at = user.get("expires_at")
        expires_text = "-"
        if expires_at:
            try:
                expires_dt = datetime.fromisoformat(expires_at)
                if expires_dt.tzinfo is None:
                    expires_dt = expires_dt.replace(tzinfo=timezone.utc)
                expires_text = expires_dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                expires_text = expires_at
        return {
            "username": user["username"],
            "role": user["role"],
            "home_dir": user["home_dir"],
            "is_temporary": bool(user.get("is_temporary", False)),
            "is_primary_admin": bool(user.get("is_primary_admin", False)),
            "expires_at": expires_at,
            "expires_at_text": expires_text,
            "created_at": user.get("created_at", ""),
        }

    def list_users(self):
        with self.lock:
            return [
                self._user_payload(user)
                for user in sorted(self._data["users"], key=lambda item: item["username"])
            ]

    def verify_user(self, username, password):
        with self.lock:
            user = self._find_user(username)
            if not user:
                return None
            if self._is_expired(user):
                return None
            seed_username = user.get("password_seed_username", user["username"])
            if user["password_hash"] != self._hash_password(seed_username, password):
                return None
            return self._user_payload(user)

    def create_user(self, username, password, role="user", expires_in_days=None, is_primary_admin=False):
        username = username.strip()
        if not username:
            raise ValueError("Username cannot be empty.")
        if role not in {"admin", "user"}:
            raise ValueError("Invalid role.")
        temporary = expires_in_days is not None
        if temporary and float(expires_in_days) <= 0:
            raise ValueError("Temporary user lifetime must be positive.")
        created_at = self._utc_now()
        expires_at = None
        if temporary:
            expires_at = (created_at + timedelta(days=float(expires_in_days))).isoformat()
        with self.lock:
            if self._find_user(username):
                raise ValueError("User already exists.")
            home_dir = username
            record = {
                "username": username,
                "password_hash": self._hash_password(username, password),
                "password_seed_username": username,
                "role": role,
                "home_dir": home_dir,
                "created_at": created_at.isoformat(),
                "is_temporary": temporary,
                "expires_at": expires_at,
                "is_primary_admin": bool(is_primary_admin),
            }
            self._data["users"].append(record)
            self._save()
        (self.storage_root / home_dir).mkdir(parents=True, exist_ok=True)
        return self._user_payload(record)

    def get_user(self, username):
        with self.lock:
            user = self._find_user(username)
            if not user:
                raise ValueError("User does not exist.")
            return self._user_payload(user)

    def reset_password(self, username, new_password):
        with self.lock:
            user = self._find_user(username)
            if not user:
                raise ValueError("User does not exist.")
            user["password_seed_username"] = user["username"]
            user["password_hash"] = self._hash_password(username, new_password)
            self._save()

    def update_user(self, current_username, new_username=None, new_password=None, new_home_dir=None):
        with self.lock:
            user = self._find_user(current_username)
            if not user:
                raise ValueError("User does not exist.")

            target_username = (new_username or current_username).strip()
            if not target_username:
                raise ValueError("Username cannot be empty.")
            existing = self._find_user(target_username)
            if existing and existing is not user:
                raise ValueError("User already exists.")

            old_snapshot = self._user_payload(dict(user))
            username_changed = target_username != user["username"]
            if username_changed:
                user.setdefault("password_seed_username", user["username"])
                user["username"] = target_username
            if new_home_dir:
                user["home_dir"] = new_home_dir
            if new_password:
                user["password_seed_username"] = user["username"]
                user["password_hash"] = self._hash_password(user["username"], new_password)
            self._save()
            return {
                "before": old_snapshot,
                "after": self._user_payload(user),
                "username_changed": username_changed,
            }

    def delete_user(self, username, remove_home=False):
        with self.lock:
            user = self._find_user(username)
            if not user:
                raise ValueError("User does not exist.")
            if user.get("is_primary_admin"):
                raise ValueError("The primary admin account cannot be removed.")
            self._data["users"] = [
                item for item in self._data["users"] if item["username"] != username
            ]
            self._save()
        if remove_home:
            shutil.rmtree(self.storage_root / user["home_dir"], ignore_errors=True)
        return user

    def purge_expired_users(self):
        now = self._utc_now()
        with self.lock:
            expired = [user for user in self._data["users"] if self._is_expired(user, now=now)]
            if not expired:
                return []
            usernames = {user["username"] for user in expired}
            self._data["users"] = [
                user for user in self._data["users"] if user["username"] not in usernames
            ]
            self._save()
        return [self._user_payload(user) for user in expired]

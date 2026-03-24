import secrets
import socket
import ssl
import threading
from datetime import datetime

from PyQt5.QtCore import QObject, pyqtSignal

from common.defaults import DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT
from common.protocol import recv_message, send_message


class TransferServer(QObject):
    log_message = pyqtSignal(str)
    stats_changed = pyqtSignal(dict)
    users_changed = pyqtSignal(list)
    sessions_changed = pyqtSignal(list)

    def __init__(self, user_store, file_storage, ssl_context=None):
        super().__init__()
        self.user_store = user_store
        self.file_storage = file_storage
        self.ssl_context = ssl_context
        self._server_socket = None
        self._accept_thread = None
        self._maintenance_thread = None
        self._maintenance_stop = threading.Event()
        self._running = False
        self._state_lock = threading.RLock()
        self._sessions = {}
        self._stats = {
            "running": False,
            "host": DEFAULT_SERVER_HOST,
            "port": DEFAULT_SERVER_PORT,
            "session_count": 0,
            "upload_bytes": 0,
            "download_bytes": 0,
        }

    def start(self, host, port):
        with self._state_lock:
            if self._running:
                return
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind((host, port))
            self._server_socket.listen(64)
            self._server_socket.settimeout(1.0)
            self._running = True
            self._stats["running"] = True
            self._stats["host"] = host
            self._stats["port"] = port
            self._maintenance_stop.clear()
            self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
            self._accept_thread.start()
            self._maintenance_thread = threading.Thread(target=self._maintenance_loop, daemon=True)
            self._maintenance_thread.start()
        self.purge_expired_users(log_removed=True)
        self._emit_users()
        self._emit_stats()
        self._log(f"Server listening on {host}:{port}")

    def stop(self):
        with self._state_lock:
            if not self._running:
                return
            self._running = False
            self._stats["running"] = False
            server_socket = self._server_socket
            self._server_socket = None
            self._maintenance_stop.set()
        if server_socket:
            try:
                server_socket.close()
            except OSError:
                pass
        self._emit_stats()
        self._log("Server stopped.")

    def is_running(self):
        with self._state_lock:
            return self._running

    def list_users(self):
        self.purge_expired_users(log_removed=True)
        return self.user_store.list_users()

    def create_user(self, username, password, role, expires_in_days=None):
        self.purge_expired_users(log_removed=True)
        user = self.user_store.create_user(username, password, role, expires_in_days=expires_in_days)
        suffix = " temporary for 1 day" if user.get("is_temporary") else ""
        self._log(f"Created user: {username} ({role}){suffix}")
        self._emit_users()
        return user

    def reset_password(self, username, password):
        self.user_store.reset_password(username, password)
        self._log(f"Password reset for user: {username}")

    def update_user(self, current_username, new_username=None, password=None):
        current_user = self.user_store.get_user(current_username)
        target_username = (new_username or current_username).strip()
        target_home_dir = current_user["home_dir"]
        if target_username and target_username != current_username:
            target_home_dir = target_username

        storage_renamed = False
        if target_home_dir != current_user["home_dir"]:
            self.file_storage.rename_user_storage(current_user["home_dir"], target_home_dir)
            storage_renamed = True
        try:
            result = self.user_store.update_user(
                current_username,
                new_username=target_username,
                new_password=password,
                new_home_dir=target_home_dir,
            )
        except Exception:
            if storage_renamed:
                self.file_storage.rename_user_storage(target_home_dir, current_user["home_dir"])
            raise

        before = result["before"]
        after = result["after"]
        with self._state_lock:
            for session in self._sessions.values():
                if session["username"] == before["username"]:
                    session["username"] = after["username"]
                    session["role"] = after["role"]
        self._log(
            f"Updated user: {before['username']}"
            + (f" -> {after['username']}" if before["username"] != after["username"] else "")
            + (" and password changed" if password else "")
        )
        self._emit_users()
        self._emit_sessions()
        self._emit_stats()
        return after

    def delete_user(self, username, remove_files=False):
        removed = self.user_store.delete_user(username, remove_home=remove_files)
        if remove_files:
            self.file_storage.delete_user_storage(removed["home_dir"])
        self._log(
            f"Deleted user: {username}"
            + (" and cleaned user storage" if remove_files else "")
        )
        self._emit_users()
        return removed

    def current_stats(self):
        with self._state_lock:
            return dict(self._stats)

    def create_folder(self, username, relative_dir, folder_name):
        created = self.file_storage.create_folder(username, relative_dir, folder_name)
        self._log(f"{username} created folder: {created}")
        return created

    def rename_entry(self, username, relative_path, new_name):
        renamed = self.file_storage.rename_entry(username, relative_path, new_name)
        self._log(f"{username} renamed entry: {relative_path} -> {renamed}")
        return renamed

    def move_entry(self, username, source_path, target_dir):
        moved = self.file_storage.move_entry(username, source_path, target_dir)
        self._log(f"{username} moved entry: {source_path} -> {moved['path']}")
        return moved

    def delete_entry(self, username, relative_path):
        deleted = self.file_storage.delete_entry(username, relative_path)
        self._log(f"{username} deleted entry: {deleted}")
        return deleted

    def purge_expired_users(self, log_removed=False):
        removed = self.user_store.purge_expired_users()
        if not removed:
            return []
        removed_names = {item["username"] for item in removed}
        for item in removed:
            self.file_storage.delete_user_storage(item["home_dir"])
            if log_removed:
                self._log(f"Expired user removed: {item['username']} and all files cleaned.")
        with self._state_lock:
            self._sessions = {
                token: session
                for token, session in self._sessions.items()
                if session["username"] not in removed_names
            }
            self._stats["session_count"] = len(self._sessions)
        self._emit_users()
        self._emit_sessions()
        self._emit_stats()
        return removed

    def _accept_loop(self):
        while self.is_running():
            try:
                client_socket, address = self._server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                secure_socket = self.ssl_context.wrap_socket(client_socket, server_side=True)
            except ssl.SSLError as exc:
                try:
                    client_socket.close()
                except OSError:
                    pass
                self._log(f"{address[0]}:{address[1]} TLS handshake failed: {exc}")
                continue
            thread = threading.Thread(
                target=self._handle_connection,
                args=(secure_socket, address),
                daemon=True,
            )
            thread.start()

    def _maintenance_loop(self):
        while not self._maintenance_stop.wait(60):
            try:
                self.purge_expired_users(log_removed=True)
            except Exception as exc:
                self._log(f"Maintenance cleanup failed: {exc}")

    def _handle_connection(self, client_socket, address):
        with client_socket:
            try:
                self.purge_expired_users(log_removed=True)
                request = recv_message(client_socket)
                action = request.get("action")
                if action == "login":
                    self._handle_login(client_socket, request, address)
                elif action == "list_files":
                    session = self._require_session(request)
                    current_dir = request.get("relative_dir", "")
                    files = self.file_storage.list_files(session["username"], current_dir)
                    send_message(
                        client_socket,
                        {
                            "status": "ok",
                            "files": files,
                            "current_dir": self.file_storage.normalize_relative_path(
                                current_dir,
                                allow_empty=True,
                            ),
                        },
                    )
                elif action == "create_folder":
                    session = self._require_session(request)
                    created = self.create_folder(
                        session["username"],
                        request.get("relative_dir", ""),
                        request["folder_name"],
                    )
                    send_message(client_socket, {"status": "ok", "path": created})
                elif action == "rename_entry":
                    session = self._require_session(request)
                    renamed = self.rename_entry(
                        session["username"],
                        request["relative_path"],
                        request["new_name"],
                    )
                    send_message(client_socket, {"status": "ok", "path": renamed})
                elif action == "move_entry":
                    session = self._require_session(request)
                    moved = self.move_entry(
                        session["username"],
                        request["source_path"],
                        request.get("target_dir", ""),
                    )
                    send_message(client_socket, {"status": "ok", **moved})
                elif action == "delete_entry":
                    session = self._require_session(request)
                    deleted = self.delete_entry(session["username"], request["relative_path"])
                    send_message(client_socket, {"status": "ok", "path": deleted})
                elif action == "prepare_upload":
                    session = self._require_session(request)
                    upload = self.file_storage.prepare_upload(
                        session["username"],
                        request["upload_id"],
                        request["filename"],
                        int(request["total_size"]),
                        int(request["chunk_size"]),
                        int(request.get("modified_time") or 0),
                    )
                    send_message(client_socket, {"status": "ok", **upload})
                elif action == "upload_chunk":
                    session = self._require_session(request)
                    complete = self.file_storage.write_upload_chunk(
                        session["username"],
                        request["upload_id"],
                        request["filename"],
                        int(request["total_size"]),
                        int(request["chunk_size"]),
                        int(request["total_chunks"]),
                        int(request["chunk_index"]),
                        int(request.get("modified_time") or 0),
                        client_socket,
                        int(request["payload_size"]),
                    )
                    self._bump_stat("upload_bytes", int(request["payload_size"]))
                    send_message(client_socket, {"status": "ok", "complete": complete})
                elif action == "prepare_download":
                    session = self._require_session(request)
                    download = self.file_storage.prepare_download(
                        session["username"],
                        request["filename"],
                        int(request["chunk_size"]),
                    )
                    send_message(client_socket, {"status": "ok", **download})
                elif action == "download_chunk":
                    session = self._require_session(request)
                    plan = self.file_storage.prepare_download(
                        session["username"],
                        request["filename"],
                        int(request["chunk_size"]),
                    )
                    chunk_size = int(request["chunk_size"])
                    chunk_index = int(request["chunk_index"])
                    total_size = plan["total_size"]
                    start = chunk_index * chunk_size
                    size = max(0, min(total_size, start + chunk_size) - start)
                    send_message(client_socket, {"status": "ok", "payload_size": size})
                    self.file_storage.stream_download_chunk(
                        session["username"],
                        request["filename"],
                        chunk_size,
                        chunk_index,
                        client_socket,
                    )
                    self._bump_stat("download_bytes", size)
                elif action == "list_users":
                    self._require_admin(request)
                    send_message(
                        client_socket,
                        {"status": "ok", "users": self.user_store.list_users()},
                    )
                elif action == "create_user":
                    self._require_admin(request)
                    user = self.create_user(
                        request["username"],
                        request["password"],
                        request.get("role", "user"),
                        request.get("expires_in_days"),
                    )
                    send_message(client_socket, {"status": "ok", "user": user})
                elif action == "reset_password":
                    self._require_admin(request)
                    self.reset_password(request["username"], request["password"])
                    send_message(client_socket, {"status": "ok"})
                elif action == "delete_user":
                    self._require_admin(request)
                    removed = self.delete_user(
                        request["username"],
                        bool(request.get("remove_files", False)),
                    )
                    send_message(client_socket, {"status": "ok", "user": removed})
                else:
                    raise ValueError("Unsupported action.")
            except Exception as exc:
                try:
                    send_message(client_socket, {"status": "error", "message": str(exc)})
                except Exception:
                    pass
                self._log(f"{address[0]}:{address[1]} error: {exc}")

    def _handle_login(self, client_socket, request, address):
        self.purge_expired_users(log_removed=True)
        user = self.user_store.verify_user(
            request.get("username", ""),
            request.get("password", ""),
        )
        if not user:
            raise ValueError("Invalid username or password.")
        token = secrets.token_hex(24)
        with self._state_lock:
            self._sessions[token] = {
                "username": user["username"],
                "role": user["role"],
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "address": f"{address[0]}:{address[1]}",
            }
            self._stats["session_count"] = len(self._sessions)
        send_message(
            client_socket,
            {
                "status": "ok",
                "token": token,
                "username": user["username"],
                "role": user["role"],
            },
        )
        self._emit_stats()
        self._emit_sessions()
        self._log(f"{user['username']} logged in from {address[0]}:{address[1]}")

    def _require_session(self, request):
        token = request.get("token", "")
        with self._state_lock:
            session = self._sessions.get(token)
        if not session:
            raise ValueError("Session is invalid or expired.")
        return session

    def _require_admin(self, request):
        session = self._require_session(request)
        if session["role"] != "admin":
            raise ValueError("Admin privileges are required.")
        return session

    def _bump_stat(self, key, amount):
        with self._state_lock:
            self._stats[key] += amount
        self._emit_stats()

    def _emit_stats(self):
        self.stats_changed.emit(self.current_stats())

    def _emit_users(self):
        self.users_changed.emit(self.user_store.list_users())

    def _emit_sessions(self):
        with self._state_lock:
            sessions = [
                {
                    "username": item["username"],
                    "role": item["role"],
                    "address": item["address"],
                    "created_at": item["created_at"],
                }
                for item in self._sessions.values()
            ]
        self.sessions_changed.emit(sessions)

    def _log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_message.emit(f"[{timestamp}] {message}")

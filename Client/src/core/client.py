import hashlib
from urllib.parse import urlparse

from common.defaults import DEFAULT_LOCAL_SERVER, DEFAULT_SERVER_PORT
from common.protocol import open_connection, recv_message, send_message
from common.security import peer_certificate_fingerprint


def parse_server_address(value):
    text = value.strip()
    if not text:
        raise ValueError("Server address cannot be empty.")
    if text.startswith("tcp://"):
        parsed = urlparse(text)
        host = parsed.hostname
        port = parsed.port
    elif ":" in text:
        host, port_text = text.rsplit(":", 1)
        host = host.strip()
        port = int(port_text)
    else:
        host = text
        port = DEFAULT_SERVER_PORT
    if not host or not port:
        raise ValueError("Server address must look like tcp://host:port.")
    return host, int(port)


class FileTransferClient:
    def __init__(self, state_store=None):
        self.server_text = DEFAULT_LOCAL_SERVER
        self.host = "127.0.0.1"
        self.port = DEFAULT_SERVER_PORT
        self.token = ""
        self.username = ""
        self.role = "user"
        self.state_store = state_store

    def configure_server(self, server_text):
        self.server_text = server_text
        self.host, self.port = parse_server_address(server_text)

    def _request(self, payload):
        with self._open_verified_connection() as connection:
            send_message(connection, payload)
            response = recv_message(connection)
        if response.get("status") != "ok":
            raise RuntimeError(response.get("message", "Unknown server error."))
        return response

    def _open_verified_connection(self):
        connection = open_connection(self.host, self.port)
        fingerprint = peer_certificate_fingerprint(connection)
        if self.state_store is not None:
            expected = self.state_store.load_server_fingerprint(self.server_text)
            if expected and expected != fingerprint:
                connection.close()
                raise RuntimeError(
                    "服务器证书指纹已变化，连接已中止。"
                    f" 当前指纹: {fingerprint}"
                )
            if not expected:
                self.state_store.save_server_fingerprint(self.server_text, fingerprint)
        return connection

    def login(self, server_text, username, password):
        self.configure_server(server_text)
        response = self._request(
            {
                "action": "login",
                "username": username,
                "password": password,
            }
        )
        self.token = response["token"]
        self.username = response["username"]
        self.role = response["role"]
        return response

    def list_files(self, relative_dir=""):
        response = self._request(
            {
                "action": "list_files",
                "token": self.token,
                "relative_dir": relative_dir,
            }
        )
        return response["files"], response.get("current_dir", relative_dir)

    def create_folder(self, relative_dir, folder_name):
        return self._request(
            {
                "action": "create_folder",
                "token": self.token,
                "relative_dir": relative_dir,
                "folder_name": folder_name,
            }
        )

    def rename_entry(self, relative_path, new_name):
        return self._request(
            {
                "action": "rename_entry",
                "token": self.token,
                "relative_path": relative_path,
                "new_name": new_name,
            }
        )

    def move_entry(self, source_path, target_dir):
        return self._request(
            {
                "action": "move_entry",
                "token": self.token,
                "source_path": source_path,
                "target_dir": target_dir,
            }
        )

    def delete_entry(self, relative_path):
        return self._request(
            {
                "action": "delete_entry",
                "token": self.token,
                "relative_path": relative_path,
            }
        )

    def prepare_upload(self, filename, total_size, chunk_size, modified_time):
        signature = hashlib.sha256(
            f"{self.username}:{filename}:{total_size}:{modified_time}".encode("utf-8")
        ).hexdigest()[:32]
        response = self._request(
            {
                "action": "prepare_upload",
                "token": self.token,
                "upload_id": signature,
                "filename": filename,
                "total_size": int(total_size),
                "chunk_size": int(chunk_size),
                "modified_time": int(modified_time),
            }
        )
        response["upload_id"] = signature
        return response

    def prepare_download(self, filename, chunk_size):
        return self._request(
            {
                "action": "prepare_download",
                "token": self.token,
                "filename": filename,
                "chunk_size": int(chunk_size),
            }
        )

    def open_transfer_connection(self, payload):
        connection = self._open_verified_connection()
        send_message(connection, payload)
        return connection

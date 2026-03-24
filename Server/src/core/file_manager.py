import json
import math
import os
import shutil
import threading
from collections import defaultdict
from pathlib import Path

from common.protocol import stream_file_to_socket, stream_socket_to_file


class FileStorage:
    def __init__(self, storage_root):
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.cache_root = self.storage_root / ".upload_cache"
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self._locks = defaultdict(threading.Lock)

    @staticmethod
    def normalize_name(name):
        filename = Path(name).name.strip()
        if not filename:
            raise ValueError("Invalid file name.")
        if filename in {".", ".."}:
            raise ValueError("Invalid file name.")
        return filename

    @staticmethod
    def normalize_relative_path(path_text, allow_empty=False):
        text = str(path_text or "").replace("\\", "/").strip().strip("/")
        if not text:
            if allow_empty:
                return ""
            raise ValueError("Invalid path.")
        parts = []
        for part in text.split("/"):
            part = part.strip()
            if not part or part == ".":
                continue
            if part == "..":
                raise ValueError("Invalid path.")
            parts.append(part)
        normalized = "/".join(parts)
        if not normalized and not allow_empty:
            raise ValueError("Invalid path.")
        return normalized

    def _resolve_user_path(self, username, relative_path="", allow_empty=True):
        root = self.user_root(username)
        normalized = self.normalize_relative_path(relative_path, allow_empty=allow_empty)
        if not normalized:
            return root, ""
        return root.joinpath(*normalized.split("/")), normalized

    def user_root(self, username):
        root = self.storage_root / username
        root.mkdir(parents=True, exist_ok=True)
        return root

    def list_files(self, username, relative_dir=""):
        files = []
        directory, normalized_dir = self._resolve_user_path(username, relative_dir, allow_empty=True)
        if not directory.exists() or not directory.is_dir():
            raise FileNotFoundError("Directory does not exist.")
        for path in sorted(directory.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
            stat = path.stat()
            files.append(
                {
                    "name": path.name,
                    "path": path.relative_to(self.user_root(username)).as_posix(),
                    "size": stat.st_size if path.is_file() else 0,
                    "modified": int(stat.st_mtime),
                    "is_dir": path.is_dir(),
                    "current_dir": normalized_dir,
                }
            )
        return files

    def _chunk_length(self, total_size, chunk_size, chunk_index):
        start = chunk_index * chunk_size
        end = min(total_size, start + chunk_size)
        return max(0, end - start)

    def _session_dir(self, username, upload_id):
        session_dir = self.cache_root / username / upload_id
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    def _manifest_path(self, username, upload_id):
        return self._session_dir(username, upload_id) / "manifest.json"

    def prepare_upload(self, username, upload_id, filename, total_size, chunk_size, modified_time):
        filename = self.normalize_relative_path(filename, allow_empty=False)
        total_chunks = max(1, math.ceil(total_size / chunk_size))
        session_dir = self._session_dir(username, upload_id)
        manifest = {
            "filename": filename,
            "total_size": total_size,
            "chunk_size": chunk_size,
            "modified_time": modified_time,
            "total_chunks": total_chunks,
        }
        with self._manifest_path(username, upload_id).open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)

        uploaded_chunks = []
        for chunk_index in range(total_chunks):
            part_path = session_dir / f"{chunk_index}.part"
            if part_path.exists() and part_path.stat().st_size == self._chunk_length(
                total_size, chunk_size, chunk_index
            ):
                uploaded_chunks.append(chunk_index)

        return {
            "filename": filename,
            "total_size": total_size,
            "chunk_size": chunk_size,
            "total_chunks": total_chunks,
            "uploaded_chunks": uploaded_chunks,
        }

    def write_upload_chunk(
        self,
        username,
        upload_id,
        filename,
        total_size,
        chunk_size,
        total_chunks,
        chunk_index,
        modified_time,
        sock,
        payload_size,
    ):
        filename = self.normalize_relative_path(filename, allow_empty=False)
        session_dir = self._session_dir(username, upload_id)
        expected_size = self._chunk_length(total_size, chunk_size, chunk_index)
        if payload_size != expected_size:
            raise ValueError("Unexpected chunk size.")
        temp_path = session_dir / f"{chunk_index}.part.tmp"
        final_part_path = session_dir / f"{chunk_index}.part"

        with temp_path.open("wb") as handle:
            stream_socket_to_file(sock, handle, payload_size)
        temp_path.replace(final_part_path)

        complete = False
        lock = self._locks[f"{username}:{upload_id}"]
        with lock:
            missing = [
                index
                for index in range(total_chunks)
                if not (session_dir / f"{index}.part").exists()
                or (session_dir / f"{index}.part").stat().st_size
                != self._chunk_length(total_size, chunk_size, index)
            ]
            if not missing:
                self._merge_chunks(
                    username,
                    upload_id,
                    filename,
                    total_size,
                    total_chunks,
                    modified_time,
                )
                complete = True
        return complete

    def _merge_chunks(self, username, upload_id, filename, total_size, total_chunks, modified_time):
        session_dir = self._session_dir(username, upload_id)
        target_path, _ = self._resolve_user_path(username, filename, allow_empty=False)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_target = target_path.with_suffix(target_path.suffix + ".uploading")

        with temp_target.open("wb") as writer:
            for chunk_index in range(total_chunks):
                part_path = session_dir / f"{chunk_index}.part"
                with part_path.open("rb") as reader:
                    shutil.copyfileobj(reader, writer, length=1024 * 1024)

        if temp_target.stat().st_size != total_size:
            raise IOError("Merged file size does not match the expected size.")
        temp_target.replace(target_path)
        if modified_time:
            os.utime(target_path, ns=(modified_time, modified_time))
        shutil.rmtree(session_dir, ignore_errors=True)

    def prepare_download(self, username, filename, chunk_size):
        path, filename = self._resolve_user_path(username, filename, allow_empty=False)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError("File does not exist.")
        total_size = path.stat().st_size
        total_chunks = max(1, math.ceil(total_size / chunk_size))
        return {
            "filename": filename,
            "total_size": total_size,
            "chunk_size": chunk_size,
            "total_chunks": total_chunks,
        }

    def stream_download_chunk(self, username, filename, chunk_size, chunk_index, sock, progress=None):
        path, filename = self._resolve_user_path(username, filename, allow_empty=False)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError("File does not exist.")
        total_size = path.stat().st_size
        payload_size = self._chunk_length(total_size, chunk_size, chunk_index)
        with path.open("rb") as handle:
            handle.seek(chunk_index * chunk_size)
            stream_file_to_socket(sock, handle, payload_size, progress=progress)
        return payload_size

    def delete_user_storage(self, storage_name):
        shutil.rmtree(self.storage_root / storage_name, ignore_errors=True)
        shutil.rmtree(self.cache_root / storage_name, ignore_errors=True)

    def create_folder(self, username, relative_dir, folder_name):
        base_dir, normalized_dir = self._resolve_user_path(username, relative_dir, allow_empty=True)
        if not base_dir.exists() or not base_dir.is_dir():
            raise FileNotFoundError("Directory does not exist.")
        target = base_dir / self.normalize_name(folder_name)
        if target.exists():
            raise ValueError("Folder already exists.")
        target.mkdir(parents=False, exist_ok=False)
        return target.relative_to(self.user_root(username)).as_posix()

    def rename_entry(self, username, relative_path, new_name):
        source, _ = self._resolve_user_path(username, relative_path, allow_empty=False)
        if not source.exists():
            raise FileNotFoundError("Entry does not exist.")
        target = source.parent / self.normalize_name(new_name)
        if target.exists():
            raise ValueError("Target name already exists.")
        source.rename(target)
        return target.relative_to(self.user_root(username)).as_posix()

    def move_entry(self, username, source_path, target_dir):
        source, _ = self._resolve_user_path(username, source_path, allow_empty=False)
        destination_dir, normalized_target = self._resolve_user_path(username, target_dir, allow_empty=True)
        if not source.exists():
            raise FileNotFoundError("Entry does not exist.")
        if not destination_dir.exists() or not destination_dir.is_dir():
            raise FileNotFoundError("Target directory does not exist.")
        target = destination_dir / source.name
        if target.exists():
            raise ValueError("Target already exists.")
        if source.is_dir():
            source_resolved = source.resolve()
            target_resolved = target.resolve(strict=False)
            if str(target_resolved).startswith(str(source_resolved) + os.sep):
                raise ValueError("Cannot move a folder into itself.")
        source.rename(target)
        return {
            "path": target.relative_to(self.user_root(username)).as_posix(),
            "target_dir": normalized_target,
        }

    def delete_entry(self, username, relative_path):
        target, normalized = self._resolve_user_path(username, relative_path, allow_empty=False)
        if not target.exists():
            raise FileNotFoundError("Entry does not exist.")
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=False)
        else:
            target.unlink()
        return normalized

    def rename_user_storage(self, old_storage_name, new_storage_name):
        old_storage = Path(old_storage_name)
        new_storage = Path(new_storage_name)
        if old_storage == new_storage:
            return
        if new_storage.name != str(new_storage):
            raise ValueError("Invalid target storage name.")

        old_root = self.storage_root / old_storage
        new_root = self.storage_root / new_storage
        if new_root.exists():
            raise ValueError("Target user directory already exists.")
        if old_root.exists():
            old_root.rename(new_root)
        else:
            new_root.mkdir(parents=True, exist_ok=True)

        old_cache = self.cache_root / old_storage
        new_cache = self.cache_root / new_storage
        if new_cache.exists():
            raise ValueError("Target user cache directory already exists.")
        if old_cache.exists():
            old_cache.rename(new_cache)

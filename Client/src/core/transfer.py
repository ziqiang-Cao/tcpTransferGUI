import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal

from common.protocol import recv_message, stream_socket_to_file


def format_speed(value):
    size = float(value)
    for unit in ["B/s", "KB/s", "MB/s", "GB/s"]:
        if size < 1024 or unit == "GB/s":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB/s"


class TransferInterrupted(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class TransferTask(QThread):
    progress_changed = pyqtSignal(int)
    speed_changed = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    completed = pyqtSignal(bool, str)

    def __init__(
        self,
        client,
        mode,
        local_path=None,
        remote_name=None,
        save_path=None,
        thread_count=4,
        chunk_size=1024 * 1024,
    ):
        super().__init__()
        self.client = client
        self.mode = mode
        self.local_path = Path(local_path) if local_path else None
        self.remote_name = remote_name
        self.save_path = Path(save_path) if save_path else None
        self.thread_count = max(1, int(thread_count))
        self.chunk_size = max(256 * 1024, int(chunk_size))
        self.total_bytes = 1
        self.completed_bytes = 0
        self._progress_lock = threading.Lock()
        self._last_emit = 0.0
        self._started_at = 0.0
        self._paused = False
        self._stop_requested = threading.Event()

    def is_paused(self):
        return self._paused

    def pause(self):
        self._paused = True
        self._stop_requested.set()
        self.status_changed.emit("已暂停")

    def resume(self):
        self._paused = False
        self._stop_requested.clear()
        if self.mode == "upload":
            self.status_changed.emit("上传中")
        else:
            self.status_changed.emit("下载中")

    def stop(self):
        self._paused = False
        self._stop_requested.set()

    def toggle_pause(self):
        if self.is_paused():
            self.resume()
        else:
            self.pause()

    def _check_interrupted(self):
        if self._stop_requested.is_set():
            reason = "__paused__" if self._paused else "__stopped__"
            raise TransferInterrupted(reason)

    def run(self):
        self._started_at = time.monotonic()
        self._stop_requested.clear()
        try:
            self._check_interrupted()
            if self.mode == "upload":
                self.status_changed.emit("准备上传")
                self._run_upload()
            elif self.mode == "download":
                self.status_changed.emit("准备下载")
                self._run_download()
            else:
                raise ValueError("Unsupported transfer mode.")
            self.progress_changed.emit(100)
            self.speed_changed.emit(
                format_speed(self.total_bytes / max(0.001, time.monotonic() - self._started_at))
            )
            self.status_changed.emit("已完成")
            self.completed.emit(True, "传输完成")
        except TransferInterrupted as exc:
            self.completed.emit(False, exc.reason)
        except Exception as exc:
            self.status_changed.emit("失败")
            self.completed.emit(False, str(exc))

    def _report_progress(self, byte_count):
        self._check_interrupted()
        with self._progress_lock:
            self.completed_bytes += byte_count
            now = time.monotonic()
            if now - self._last_emit < 0.08 and self.completed_bytes < self.total_bytes:
                return
            self._last_emit = now
            progress = int((self.completed_bytes / max(1, self.total_bytes)) * 100)
            speed = self.completed_bytes / max(0.001, now - self._started_at)
        self.progress_changed.emit(min(progress, 100))
        self.speed_changed.emit(format_speed(speed))

    def _chunk_length(self, total_size, index):
        start = index * self.chunk_size
        end = min(total_size, start + self.chunk_size)
        return max(0, end - start)

    def _run_upload(self):
        file_size = self.local_path.stat().st_size
        modified_time = int(self.local_path.stat().st_mtime_ns)
        filename = self.remote_name or self.local_path.name
        plan = self.client.prepare_upload(filename, file_size, self.chunk_size, modified_time)
        total_chunks = int(plan["total_chunks"])
        uploaded = set(plan["uploaded_chunks"])
        self.total_bytes = file_size
        self.completed_bytes = sum(self._chunk_length(file_size, index) for index in uploaded)
        self._report_progress(0)
        pending = [index for index in range(total_chunks) if index not in uploaded]
        if not pending:
            return

        self.status_changed.emit("上传中")
        with ThreadPoolExecutor(max_workers=min(self.thread_count, len(pending))) as executor:
            futures = [
                executor.submit(
                    self._upload_chunk,
                    filename,
                    plan["upload_id"],
                    file_size,
                    total_chunks,
                    modified_time,
                    chunk_index,
                )
                for chunk_index in pending
            ]
            for future in as_completed(futures):
                future.result()

    def _upload_chunk(self, filename, upload_id, total_size, total_chunks, modified_time, chunk_index):
        payload_size = self._chunk_length(total_size, chunk_index)
        connection = self.client.open_transfer_connection(
            {
                "action": "upload_chunk",
                "token": self.client.token,
                "upload_id": upload_id,
                "filename": filename,
                "total_size": total_size,
                "chunk_size": self.chunk_size,
                "total_chunks": total_chunks,
                "chunk_index": chunk_index,
                "modified_time": modified_time,
                "payload_size": payload_size,
            }
        )
        try:
            with self.local_path.open("rb") as handle:
                handle.seek(chunk_index * self.chunk_size)
                remaining = payload_size
                while remaining > 0:
                    self._check_interrupted()
                    data = handle.read(min(64 * 1024, remaining))
                    if not data:
                        raise IOError("Unexpected end of local file.")
                    connection.sendall(data)
                    remaining -= len(data)
                    self._report_progress(len(data))
            self._check_interrupted()
            response = recv_message(connection)
            if response.get("status") != "ok":
                raise RuntimeError(response.get("message", "Upload chunk failed."))
        finally:
            connection.close()

    def _run_download(self):
        plan = self.client.prepare_download(self.remote_name, self.chunk_size)
        total_size = int(plan["total_size"])
        total_chunks = int(plan["total_chunks"])
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        cache_dir = self.save_path.parent / f".{self.save_path.name}.parts"
        cache_dir.mkdir(parents=True, exist_ok=True)

        completed = set()
        self.total_bytes = total_size
        self.completed_bytes = 0
        for chunk_index in range(total_chunks):
            part_path = cache_dir / f"{chunk_index}.part"
            expected = self._chunk_length(total_size, chunk_index)
            if part_path.exists() and part_path.stat().st_size == expected:
                completed.add(chunk_index)
                self.completed_bytes += expected
        self._report_progress(0)

        pending = [index for index in range(total_chunks) if index not in completed]
        if pending:
            self.status_changed.emit("下载中")
            with ThreadPoolExecutor(max_workers=min(self.thread_count, len(pending))) as executor:
                futures = [
                    executor.submit(
                        self._download_chunk,
                        cache_dir,
                        chunk_index,
                    )
                    for chunk_index in pending
                ]
                for future in as_completed(futures):
                    future.result()

        temp_path = self.save_path.with_suffix(self.save_path.suffix + ".downloading")
        with temp_path.open("wb") as writer:
            for chunk_index in range(total_chunks):
                with (cache_dir / f"{chunk_index}.part").open("rb") as reader:
                    shutil.copyfileobj(reader, writer, length=1024 * 1024)
        temp_path.replace(self.save_path)
        shutil.rmtree(cache_dir, ignore_errors=True)

    def _download_chunk(self, cache_dir, chunk_index):
        connection = self.client.open_transfer_connection(
            {
                "action": "download_chunk",
                "token": self.client.token,
                "filename": self.remote_name,
                "chunk_size": self.chunk_size,
                "chunk_index": chunk_index,
            }
        )
        try:
            self._check_interrupted()
            response = recv_message(connection)
            if response.get("status") != "ok":
                raise RuntimeError(response.get("message", "Download chunk failed."))
            payload_size = int(response["payload_size"])
            temp_path = cache_dir / f"{chunk_index}.part.tmp"
            final_path = cache_dir / f"{chunk_index}.part"
            with temp_path.open("wb") as handle:
                stream_socket_to_file(connection, handle, payload_size, progress=self._report_progress)
            self._check_interrupted()
            temp_path.replace(final_path)
        finally:
            connection.close()

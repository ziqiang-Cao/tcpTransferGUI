import json
import socket
import struct

from common.security import create_client_ssl_context


HEADER_SIZE = 4
MAX_MESSAGE_SIZE = 8 * 1024 * 1024
STREAM_BLOCK_SIZE = 64 * 1024


class ProtocolError(Exception):
    pass


def recv_exact(sock, size):
    chunks = bytearray()
    while len(chunks) < size:
        data = sock.recv(size - len(chunks))
        if not data:
            raise ConnectionError("Connection closed unexpectedly.")
        chunks.extend(data)
    return bytes(chunks)


def send_message(sock, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(body) > MAX_MESSAGE_SIZE:
        raise ProtocolError("Message is too large.")
    sock.sendall(struct.pack("!I", len(body)))
    sock.sendall(body)


def recv_message(sock):
    raw_size = recv_exact(sock, HEADER_SIZE)
    size = struct.unpack("!I", raw_size)[0]
    if size > MAX_MESSAGE_SIZE:
        raise ProtocolError("Incoming message is too large.")
    body = recv_exact(sock, size)
    return json.loads(body.decode("utf-8"))


def stream_socket_to_file(sock, file_obj, total_size, progress=None):
    remaining = total_size
    while remaining > 0:
        chunk = sock.recv(min(STREAM_BLOCK_SIZE, remaining))
        if not chunk:
            raise ConnectionError("Connection closed during data transfer.")
        file_obj.write(chunk)
        remaining -= len(chunk)
        if progress:
            progress(len(chunk))


def stream_file_to_socket(sock, file_obj, total_size, progress=None):
    remaining = total_size
    while remaining > 0:
        chunk = file_obj.read(min(STREAM_BLOCK_SIZE, remaining))
        if not chunk:
            raise IOError("Unexpected end of file during transfer.")
        sock.sendall(chunk)
        remaining -= len(chunk)
        if progress:
            progress(len(chunk))


def open_connection(host, port, timeout=10):
    connection = socket.create_connection((host, port), timeout=timeout)
    connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    secure_connection = create_client_ssl_context().wrap_socket(connection, server_hostname=host)
    secure_connection.settimeout(timeout)
    return secure_connection

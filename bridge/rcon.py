"""Minimal, dependency-free Factorio RCON client (Source RCON framing)."""
from __future__ import annotations

import socket
import struct
import threading
import time
from dataclasses import dataclass


class RconError(RuntimeError):
    pass


@dataclass
class RconPacket:
    request_id: int
    type: int
    body: str


class RconClient:
    """Synchronous Factorio RCON client.

    Packet layout (little endian)::

        int32 length | int32 id | int32 type | body | 0x00 0x00

    ``length`` counts id + type + body + two NUL bytes.
    Types: 3 = auth, 2 = exec, 0 = response.
    """

    AUTH = 3
    EXEC = 2
    RESPONSE = 0

    def __init__(self, host: str = "127.0.0.1", port: int = 27015,
                 password: str = "", timeout: float = 5.0):
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._id = 0
        self._lock = threading.Lock()

    def connect(self) -> "RconClient":
        self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self._sock.settimeout(self.timeout)
        self._auth()
        return self

    def _next_id(self) -> int:
        self._id = (self._id + 1) % 2_000_000_000
        return self._id

    def _send(self, req_id: int, ptype: int, body: str) -> None:
        assert self._sock is not None
        payload = struct.pack("<ii", req_id, ptype) + body.encode("utf-8") + b"\x00\x00"
        self._sock.sendall(struct.pack("<i", len(payload)) + payload)

    def _recv_exact(self, n: int) -> bytes:
        assert self._sock is not None
        buf = bytearray()
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                raise RconError("RCON connection closed")
            buf.extend(chunk)
        return bytes(buf)

    def _recv(self) -> RconPacket:
        (length,) = struct.unpack("<i", self._recv_exact(4))
        if length < 10 or length > 100 * 1024 * 1024:
            raise RconError(f"invalid RCON frame length {length}")
        data = self._recv_exact(length)
        req_id, ptype = struct.unpack("<ii", data[:8])
        body = data[8:-2].decode("utf-8", "replace")
        return RconPacket(req_id, ptype, body)

    def _auth(self) -> None:
        req_id = self._next_id()
        self._send(req_id, self.AUTH, self.password)
        resp = self._recv()
        if resp.request_id == -1:
            raise RconError("RCON authentication failed (bad password)")
        if resp.request_id != req_id or resp.type != 2:
            raise RconError(f"unexpected auth response: {resp}")

    def execute(self, command: str, timeout: float | None = None) -> str:
        """Run one console command and return its output.

        Factorio answers a command with one or more type-0 packets; the first
        packet with the matching id terminates the command in practice.  Some
        commands emit no packet at all, so a timeout yields "".
        """
        with self._lock:
            assert self._sock is not None
            req_id = self._next_id()
            self._send(req_id, self.EXEC, command)
            old = self._sock.gettimeout()
            if timeout is not None:
                self._sock.settimeout(timeout)
            chunks: list[str] = []
            try:
                while True:
                    pkt = self._recv()
                    if pkt.request_id == req_id and pkt.type == self.RESPONSE:
                        chunks.append(pkt.body)
                        # Factorio sends one packet per command; empty body = no output
                        break
            except socket.timeout:
                pass
            finally:
                self._sock.settimeout(old)
            return "".join(chunks)

    def close(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *exc):
        self.close()


def lua_quote(value: str) -> str:
    """Quote a Python string as a Lua string literal."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def call_interface(rcon: RconClient, interface: str, method: str, *args) -> str:
    """Invoke a mod remote interface via the server console."""
    rendered = ", ".join(lua_quote(a) if isinstance(a, str) else str(a) for a in args)
    command = f'/c remote.call({lua_quote(interface)}, {lua_quote(method)}'
    if rendered:
        command += ", " + rendered
    command += ")"
    return rcon.execute(command)


if __name__ == "__main__":
    import sys
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 27016
    password = sys.argv[3] if len(sys.argv) > 3 else "test"
    command = sys.argv[4] if len(sys.argv) > 4 else '/c rcon.print("hello "..game.tick)'
    with RconClient(host, port, password) as rc:
        print(rc.execute(command))

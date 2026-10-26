"""Probe Factorio's RCON wire format (Source-RCON-like) without third-party deps."""
import socket
import struct
import sys
import json

HOST = "127.0.0.1"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 27015
PASSWORD = sys.argv[2] if len(sys.argv) > 2 else "test"


def frame(req_id: int, ptype: int, body: str) -> bytes:
    payload = struct.pack("<ii", req_id, ptype) + body.encode("utf-8") + b"\x00\x00"
    return struct.pack("<i", len(payload)) + payload


def recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise EOFError("connection closed")
        buf += chunk
    return buf


def recv_frame(sock: socket.socket):
    (length,) = struct.unpack("<i", recv_exact(sock, 4))
    payload = recv_exact(sock, length)
    req_id, ptype = struct.unpack("<ii", payload[:8])
    body = payload[8:-2].decode("utf-8", "replace")
    return length, req_id, ptype, body


def main():
    s = socket.create_connection((HOST, PORT), timeout=5)
    s.settimeout(2)
    print("auth ->", frame(1, 3, PASSWORD).hex())
    s.sendall(frame(1, 3, PASSWORD))
    print("auth resp:", recv_frame(s))

    cmd = sys.argv[3] if len(sys.argv) > 3 else '/c rcon.print("hello from rcon tick="..game.tick)'
    s.sendall(frame(2, 2, cmd))
    while True:
        try:
            fr = recv_frame(s)
        except socket.timeout:
            print("(timeout, no more frames)")
            break
        print("resp:", fr)
        if fr[1] == 2 and fr[2] == 0 and fr[3] == "":
            break
    s.close()


if __name__ == "__main__":
    main()

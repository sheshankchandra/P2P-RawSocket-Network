# Custom packet framing over TCP sockets

import struct
from .constants import MAGIC_BYTES, PROTOCOL_VERSION, HEADER_FORMAT, FLAG_NONE

class P2PPacket:
    def __init__(self, msg_type: int, payload: bytes = b"", seq_num: int = 0, flags: int = FLAG_NONE, version: int = PROTOCOL_VERSION):
        self.magic = MAGIC_BYTES
        self.version = version
        self.msg_type = msg_type
        self.flags = flags
        self.seq_num = seq_num
        self.payload = payload
        self.payload_len = len(payload)
        self.checksum = 0

    def to_bytes(self) -> bytes:
        header = struct.pack(HEADER_FORMAT, self.magic, self.version, self.msg_type, self.flags, self.seq_num, self.payload_len, self.checksum)
        return header + self.payload

    def __repr__(self):
        return f"<P2PPacket type={self.msg_type:#04x} len={self.payload_len}>"

class ConnectionClosedError(Exception):
    pass

def recv_exact(sock, num_bytes: int) -> bytes:
    buffer = bytearray()
    while len(buffer) < num_bytes:
        chunk = sock.recv(num_bytes - len(buffer))
        if not chunk:
            if len(buffer) == 0:
                raise ConnectionClosedError("Remote peer closed the connection.")
            raise ConnectionClosedError(f"Connection dropped mid-stream (needed {num_bytes}, got {len(buffer)})")
        buffer.extend(chunk)
    return bytes(buffer)

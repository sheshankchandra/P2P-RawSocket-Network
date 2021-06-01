# Custom packet framing over TCP sockets.
# Uses 'construct' to parse the binary header easily without manual slicing.

import zlib
import socket
from typing import Optional
from .constants import (
    MAGIC_BYTES,
    PROTOCOL_VERSION,
    HEADER_SIZE,
    FLAG_NONE,
    MAX_PAYLOAD_SIZE,
)

try:
    from construct import Struct, Const, Byte, Int16ub, Int32ub

    # 20-byte header format:
    # 4 bytes magic, 1 byte version, 1 byte opcode, 2 bytes flags,
    # 4 bytes sequence number, 4 bytes payload length, 4 bytes CRC32 checksum
    P2PHeaderConstruct = Struct(
        "magic" / Const(MAGIC_BYTES),
        "version" / Byte,
        "msg_type" / Byte,
        "flags" / Int16ub,
        "seq_num" / Int32ub,
        "payload_len" / Int32ub,
        "checksum" / Int32ub,
    )
    USE_CONSTRUCT = True
except ImportError:
    import struct
    from .constants import HEADER_FORMAT
    USE_CONSTRUCT = False


class InvalidPacketError(Exception):
    pass


class ConnectionClosedError(Exception):
    pass


class P2PPacket:
    def __init__(
        self,
        msg_type: int,
        payload: bytes = b"",
        seq_num: int = 0,
        flags: int = FLAG_NONE,
        version: int = PROTOCOL_VERSION,
    ):
        self.magic = MAGIC_BYTES
        self.version = version
        self.msg_type = msg_type
        self.flags = flags
        self.seq_num = seq_num
        self.payload = payload
        self.payload_len = len(payload)
        self.checksum = zlib.crc32(payload) & 0xFFFFFFFF

    def to_bytes(self) -> bytes:
        # Pack header with Big-Endian byte order so different machines can talk
        if USE_CONSTRUCT:
            header_bytes = P2PHeaderConstruct.build({
                "version": self.version,
                "msg_type": self.msg_type,
                "flags": self.flags,
                "seq_num": self.seq_num,
                "payload_len": self.payload_len,
                "checksum": self.checksum,
            })
        else:
            import struct
            from .constants import HEADER_FORMAT
            header_bytes = struct.pack(
                HEADER_FORMAT,
                self.magic,
                self.version,
                self.msg_type,
                self.flags,
                self.seq_num,
                self.payload_len,
                self.checksum,
            )
        return header_bytes + self.payload

    @classmethod
    def from_header_and_payload(
        cls,
        magic: bytes,
        version: int,
        msg_type: int,
        flags: int,
        seq_num: int,
        payload_len: int,
        checksum: int,
        payload: bytes,
    ) -> "P2PPacket":
        if magic != MAGIC_BYTES:
            raise InvalidPacketError(f"Bad magic bytes: expected {MAGIC_BYTES!r}, got {magic!r}")

        if version != PROTOCOL_VERSION:
            raise InvalidPacketError(f"Unsupported version: {version}")

        if len(payload) != payload_len:
            raise InvalidPacketError(f"Length mismatch: header says {payload_len}, got {len(payload)}")

        # Check payload integrity
        computed_crc = zlib.crc32(payload) & 0xFFFFFFFF
        if computed_crc != checksum:
            raise InvalidPacketError(f"Checksum mismatch: expected {checksum:#x}, got {computed_crc:#x}")

        return cls(
            msg_type=msg_type,
            payload=payload,
            seq_num=seq_num,
            flags=flags,
            version=version,
        )

    def __repr__(self) -> str:
        return f"<P2PPacket type={self.msg_type:#04x} seq={self.seq_num} len={self.payload_len}>"


def recv_exact(sock: socket.socket, num_bytes: int) -> bytes:
    # TCP doesn't guarantee getting all bytes in a single recv() call,
    # so we loop until we have exactly what we need.
    buffer = bytearray()
    while len(buffer) < num_bytes:
        chunk = sock.recv(num_bytes - len(buffer))
        if not chunk:
            if len(buffer) == 0:
                raise ConnectionClosedError("Remote peer closed the connection.")
            raise ConnectionClosedError(f"Connection dropped mid-stream (needed {num_bytes}, got {len(buffer)})")
        buffer.extend(chunk)
    return bytes(buffer)


def read_packet(sock: socket.socket) -> P2PPacket:
    # 1. Read fixed 20-byte header
    header_raw = recv_exact(sock, HEADER_SIZE)

    if USE_CONSTRUCT:
        try:
            parsed = P2PHeaderConstruct.parse(header_raw)
            magic = MAGIC_BYTES
            version = parsed.version
            msg_type = parsed.msg_type
            flags = parsed.flags
            seq_num = parsed.seq_num
            payload_len = parsed.payload_len
            checksum = parsed.checksum
        except Exception as e:
            raise InvalidPacketError(f"Failed to parse packet header: {e}")
    else:
        import struct
        from .constants import HEADER_FORMAT
        magic, version, msg_type, flags, seq_num, payload_len, checksum = struct.unpack(
            HEADER_FORMAT, header_raw
        )

    if payload_len > MAX_PAYLOAD_SIZE:
        raise InvalidPacketError(f"Payload too large ({payload_len} bytes)")

    # 2. Read exactly payload_len bytes
    payload = recv_exact(sock, payload_len) if payload_len > 0 else b""

    return P2PPacket.from_header_and_payload(
        magic=magic,
        version=version,
        msg_type=msg_type,
        flags=flags,
        seq_num=seq_num,
        payload_len=payload_len,
        checksum=checksum,
        payload=payload,
    )


def send_packet(sock: socket.socket, packet: P2PPacket) -> None:
    sock.sendall(packet.to_bytes())

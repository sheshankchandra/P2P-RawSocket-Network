# Protocol Specification

This document describes the binary packet format used by the peers to talk to each other over TCP.

---

## 1. Packet Structure

TCP is a stream of bytes, not packets. If you send two messages, `recv()` might read half of one message or both messages combined. To solve this, every message has a fixed 20-byte header:

```
+-------------------------------------------------------------------+
| Magic (4B) | Ver (1B) | Type (1B) | Flags (2B) | Seq (4B) | Len (4B) | CRC32 (4B) |
+-------------------------------------------------------------------+
| Payload (variable length, specified by Len)                      |
+-------------------------------------------------------------------+
```

### Header Fields

| Field | Size | Description |
|---|---|---|
| Magic | 4 bytes | Always ASCII `P2PF` (`0x50325046`). Identifies the packet. |
| Version | 1 byte | Protocol version (`1`). |
| Type | 1 byte | Message opcode (e.g. handshake, chunk request). |
| Flags | 2 bytes | Optional flags (e.g. compression). |
| Seq | 4 bytes | Sequence number or request ID. |
| Len | 4 bytes | Length of the payload following this header. |
| CRC32 | 4 bytes | CRC-32 checksum of the payload to detect bit corruption. |

Byte order is Big-Endian (`!` in Python `struct` / `construct`).

---

## 2. Reading a Packet

1. Read exactly 20 bytes to get the header.
2. Unpack the header fields and read `payload_len`.
3. Read exactly `payload_len` bytes from the socket.
4. Calculate CRC-32 on the received payload and compare with the checksum in the header. If they don't match, drop the packet.

---

## 3. Message Types (Opcodes)

| Opcode | Name | Purpose |
|---|---|---|
| `0x01` | `OP_HANDSHAKE` | Sent when first connecting to identify node ID. |
| `0x02` | `OP_HANDSHAKE_ACK` | Handshake response acknowledging connection. |
| `0x03` | `OP_PING` | Heartbeat check to see if peer is responsive. |
| `0x04` | `OP_PONG` | Response to ping. |
| `0x05` | `OP_FILE_LIST_REQ` | Ask peer for their shared files list. |
| `0x06` | `OP_FILE_LIST_RESP` | Returns list of available files. |
| `0x07` | `OP_FILE_META_REQ` | Request file manifest (chunk count, size, hashes). |
| `0x08` | `OP_FILE_META_RESP` | Returns the file manifest. |
| `0x09` | `OP_CHUNK_REQ` | Request a specific chunk index of a file. |
| `0x0A` | `OP_CHUNK_RESP` | Delivers the binary chunk data. |
| `0x0B` | `OP_HAVE_CHUNK` | Announce that a new chunk was downloaded. |
| `0xFF` | `OP_ERROR` | Error message payload. |

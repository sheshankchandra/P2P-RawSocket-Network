# Protocol constants and message types

# Magic bytes to identify packets belonging to this app ("P2PF")
MAGIC_BYTES = b"P2PF"
PROTOCOL_VERSION = 1

# Fixed 20-byte header format:
# magic(4s), version(B), msg_type(B), flags(H), seq_num(I), payload_len(I), crc32(I)
HEADER_FORMAT = "!4sBBHIII"
HEADER_SIZE = 20

# Message types (opcodes)
OP_HANDSHAKE       = 0x01
OP_HANDSHAKE_ACK   = 0x02
OP_PING            = 0x03
OP_PONG            = 0x04
OP_FILE_LIST_REQ   = 0x05
OP_FILE_LIST_RESP  = 0x06
OP_FILE_META_REQ   = 0x07
OP_FILE_META_RESP  = 0x08
OP_CHUNK_REQ       = 0x09
OP_CHUNK_RESP      = 0x0A
OP_HAVE_CHUNK      = 0x0B
OP_ERROR           = 0xFF

# Header flags
FLAG_NONE          = 0x0000
FLAG_COMPRESSED    = 0x0001
FLAG_URGENT        = 0x0002

# Default networking settings
DEFAULT_CHUNK_SIZE = 64 * 1024  # 64 KB chunks
DEFAULT_UDP_PORT   = 9876       # UDP broadcast port for peer discovery
DEFAULT_TCP_PORT   = 6001       # TCP port for file transfers
BROADCAST_INTERVAL = 3.0        # Send discovery beacon every 3s
PEER_TIMEOUT_SEC   = 10.0       # Drop peer if no beacon heard for 10s
SOCKET_TIMEOUT     = 5.0
MAX_PAYLOAD_SIZE   = 16 * 1024 * 1024  # 16 MB limit to avoid runaway memory

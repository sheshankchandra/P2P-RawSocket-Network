# Protocol constants and message types

MAGIC_BYTES = b"P2PF"
PROTOCOL_VERSION = 1

OP_HANDSHAKE       = 0x01
OP_HANDSHAKE_ACK   = 0x02
OP_PING            = 0x03
OP_PONG            = 0x04
OP_FILE_LIST_REQ   = 0x05
OP_FILE_LIST_RESP  = 0x06

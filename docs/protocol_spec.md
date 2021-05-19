# Protocol Specification (Draft)

Initial ideas on TCP packet framing for P2P chunk transfer.
TCP is a byte stream, so we need a fixed header to determine packet boundaries.
Header layout:
- 4 bytes: Magic bytes
- 1 byte: Version
- 1 byte: Message Type (opcode)
- 4 bytes: Payload Length

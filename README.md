# P2P File Sharing

A small peer-to-peer file sharing program built with Python sockets to learn how distributed file transfers, packet framing, and piece-wise downloading work under the hood.

Instead of using HTTP or web frameworks, this project communicates directly over TCP and UDP sockets with a custom binary packet protocol.

---

## Features

- Custom binary wire protocol: 20-byte fixed header with magic bytes, length, sequence numbers, and CRC-32 checksums to handle TCP streaming and packet boundaries.
- Chunk-based file transfers: Files are split into 64 KB chunks, each verified with SHA-256.
- Parallel swarm downloading: Downloads different chunks concurrently from multiple peers and reassembles them in order.
- LAN peer discovery: Uses UDP broadcast heartbeats so peers on the same network find each other automatically.
- Piece bitfield tracking: Uses `bitarray` to track which pieces a peer has.
- Dual interface: An interactive terminal CLI (using `rich`) and a basic Tkinter desktop GUI.
- Packet inspection tool: A small helper using `scapy` to see IP/TCP packet headers and custom protocol frames.

---

## Installation

Clone the repository and install the dependencies:

```bash
pip install -r requirements.txt
```

Libraries used:
- `construct` - Declarative binary packet header packing/unpacking
- `bitarray` - Compact bitfield tracking for file pieces
- `rich` - Terminal tables and progress bars
- `scapy` - Optional packet dissection for the sniffer utility

---

## Quick Start

### 1. Run the local simulation test

This spawns 3 nodes (Alice, Bob, and Charlie) locally, shares a test file, downloads chunks in parallel across peers, and checks the SHA-256 hashes:

```bash
python test_simulation.py
```

### 2. Run via Terminal (CLI)

Start peer 1 (Alice):
```bash
python run_peer.py --id Alice --tcp 6001
```

Inside Alice's terminal, share a file:
```text
(Alice)> share ./my_file.pdf
(Alice)> myfiles
```

In a second terminal, start peer 2 (Bob):
```bash
python run_peer.py --id Bob --tcp 6002
```

Inside Bob's terminal, look for peers and download:
```text
(Bob)> peers
(Bob)> networkfiles
(Bob)> download <file_id>
```

### 3. Run via Desktop GUI

You can also launch a Tkinter interface:

```bash
python run_peer.py --id Alice --tcp 6001 --gui
python run_peer.py --id Bob --tcp 6002 --gui
```

---

## Project Structure

```
P2P-RawSocket-Network/
├── README.md              # Project overview and quick start
├── requirements.txt       # Dependencies
├── run_peer.py            # Main entry point (CLI / GUI)
├── test_simulation.py     # 3-node local test script
├── protocol/
│   ├── constants.py       # Magic bytes, opcodes, header format
│   ├── packet.py          # Packet class, construct parser, recv_exact()
│   └── serializer.py      # Payload encoders/decoders
├── core/
│   ├── chunker.py         # File splitting, SHA-256 hashing, bitfield
│   ├── file_manager.py    # Local storage indexing and piece reading
│   ├── peer_discovery.py  # UDP broadcast discovery
│   ├── transfer_engine.py # Multi-peer chunk downloader
│   └── raw_socket_helper.py # Packet sniffer using scapy
├── node/
│   └── peer_node.py       # PeerNode combining server and client
├── ui/
│   ├── cli.py             # Terminal REPL
│   └── gui.py             # Tkinter desktop GUI
└── docs/
    ├── architecture.md    # Overview of chunks, discovery, and transfers
    └── protocol_spec.md   # Packet header layout and opcodes
```

---

## Documentation

More details can be found in the `docs` folder:
- [Architecture](docs/architecture.md): How chunking, peer discovery, and parallel transfers work.
- [Protocol Specification](docs/protocol_spec.md): The 20-byte binary header layout and opcode list.

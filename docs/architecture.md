# Project Architecture

A quick overview of how the pieces connect together.

---

## 1. File Chunking & Manifests

- Files shared in the network are split into fixed 64 KB pieces.
- For each piece, we calculate a SHA-256 hash.
- The whole file also has a SHA-256 hash which acts as the unique `file_id`.
- The metadata dictionary (manifest) contains:
  - `file_id`: file hash
  - `file_name`: name of file
  - `file_size`: size in bytes
  - `chunk_size`: 65,536 bytes
  - `chunk_count`: total pieces
  - `chunk_hashes`: list of individual piece hashes

---

## 2. Bitfield Piece Tracking

To track which chunks of a file a peer has, we use a `bitarray`.
For a file with 8 chunks:
- A peer that has all pieces: `bitarray('11111111')`
- A peer that has chunks 0, 1, and 4: `bitarray('11001000')`

This is much more compact than passing lists of chunk numbers around.

---

## 3. Peer Discovery (UDP)

- Each node runs a background thread that sends a small JSON heartbeat over UDP broadcast (`255.255.255.255:9876`) every 3 seconds.
- Other nodes running on the same network or subnet listen on UDP port 9876.
- When a beacon arrives, the node adds the remote peer's IP and TCP port to its known peers table.
- Peers that haven't sent a beacon in over 10 seconds are pruned.

---

## 4. Swarm Transfers (TCP)

- When downloading a file:
  1. The node queries known peers to see who has the file.
  2. It fetches the manifest (list of chunk hashes) from one peer.
  3. It creates a queue with chunk indices (`0, 1, 2, ...`).
  4. Worker threads pull chunk indices from the queue and request them over TCP from available seeders in parallel.
  5. When a chunk arrives, its SHA-256 hash is checked against the manifest. If it doesn't match, it gets re-queued.
  6. Once all chunks arrive, they are written sequentially to disk and the final file hash is verified.
  7. The node marks the file as complete in its storage and begins seeding it to others.

---

## 5. Error Detection

- **Per-packet CRC-32**: Catches bit flips or truncated network packets at the framing layer.
- **Per-chunk SHA-256**: Catches corrupted or modified file chunks.
- **Full file SHA-256**: Ensures the reassembled file matches the original byte-for-byte.

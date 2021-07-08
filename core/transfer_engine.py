# Downloads file chunks in parallel from multiple peers.
# Chunks are verified against the manifest SHA-256 hashes as they arrive.

import time
import queue
import socket
import threading
from typing import Dict, List, Optional, Callable
from protocol.constants import (
    OP_CHUNK_REQ,
    OP_CHUNK_RESP,
    SOCKET_TIMEOUT,
)
from protocol.packet import P2PPacket, read_packet, send_packet
from protocol.serializer import encode_chunk_req, decode_chunk_resp
from .chunker import FileManifest, verify_chunk, reassemble_file


class SwarmDownloader:
    def __init__(
        self,
        manifest: FileManifest,
        output_filepath: str,
        peer_addresses: List[tuple[str, int]],
        max_workers: int = 4,
        progress_cb: Optional[Callable[[int, int, float], None]] = None,
    ):
        self.manifest = manifest
        self.output_filepath = output_filepath
        self.peer_addresses = peer_addresses
        self.max_workers = min(max_workers, len(peer_addresses) * 2, manifest.chunk_count)
        self.progress_cb = progress_cb

        # Queue of chunk indices that need to be downloaded
        self.chunk_queue: queue.Queue = queue.Queue()
        for idx in range(manifest.chunk_count):
            self.chunk_queue.put(idx)

        self.received_chunks: Dict[int, bytes] = {}
        self.chunks_lock = threading.Lock()

        self.is_cancelled = False
        self.total_bytes = manifest.file_size
        self.downloaded_bytes = 0
        self.start_time = 0.0

    def start_download(self) -> bool:
        if not self.peer_addresses:
            raise ValueError("No peers available to download from.")

        self.start_time = time.time()
        threads = []
        num_workers = max(1, self.max_workers)

        for worker_id in range(num_workers):
            peer_ip, peer_port = self.peer_addresses[worker_id % len(self.peer_addresses)]
            t = threading.Thread(
                target=self._worker_loop,
                args=(peer_ip, peer_port),
                name=f"Downloader-{worker_id}",
                daemon=True,
            )
            threads.append(t)
            t.start()

        # Wait until all chunks are downloaded
        self.chunk_queue.join()

        self.is_cancelled = True
        for t in threads:
            t.join(timeout=2.0)

        with self.chunks_lock:
            if len(self.received_chunks) != self.manifest.chunk_count:
                raise RuntimeError(
                    f"Download incomplete: got {len(self.received_chunks)} of {self.manifest.chunk_count} chunks"
                )

        # Write pieces in order and verify overall hash
        reassemble_file(self.output_filepath, self.received_chunks, self.manifest)
        return True

    def _worker_loop(self, peer_ip: str, peer_port: int):
        # Worker keeps a TCP connection open to a peer and requests chunks one by one
        sock = None
        while not self.is_cancelled:
            try:
                try:
                    chunk_idx = self.chunk_queue.get(timeout=1.0)
                except queue.Empty:
                    break

                if sock is None:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(SOCKET_TIMEOUT)
                    sock.connect((peer_ip, peer_port))

                # Request chunk
                payload = encode_chunk_req(self.manifest.file_id, chunk_idx)
                req_packet = P2PPacket(msg_type=OP_CHUNK_REQ, payload=payload, seq_num=chunk_idx)
                send_packet(sock, req_packet)

                # Read response
                resp_packet = read_packet(sock)
                if resp_packet.msg_type != OP_CHUNK_RESP:
                    # Put chunk back in queue and reset connection
                    self.chunk_queue.put(chunk_idx)
                    self.chunk_queue.task_done()
                    if sock:
                        sock.close()
                        sock = None
                    time.sleep(0.5)
                    continue

                file_id, resp_idx, chunk_data = decode_chunk_resp(resp_packet.payload)

                # Verify piece hash
                expected_hash = self.manifest.chunk_hashes[chunk_idx]
                if not verify_chunk(chunk_data, expected_hash):
                    # Corrupted chunk, re-queue so another worker tries
                    self.chunk_queue.put(chunk_idx)
                    self.chunk_queue.task_done()
                    continue

                with self.chunks_lock:
                    self.received_chunks[chunk_idx] = chunk_data
                    self.downloaded_bytes += len(chunk_data)
                    completed = len(self.received_chunks)

                self.chunk_queue.task_done()

                # Report progress
                if self.progress_cb:
                    elapsed = max(0.001, time.time() - self.start_time)
                    speed_kbs = (self.downloaded_bytes / 1024.0) / elapsed
                    self.progress_cb(completed, self.manifest.chunk_count, speed_kbs)

            except Exception:
                try:
                    self.chunk_queue.task_done()
                    self.chunk_queue.put(chunk_idx)
                except Exception:
                    pass
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass
                    sock = None
                time.sleep(0.5)

        if sock:
            try:
                sock.close()
            except Exception:
                pass

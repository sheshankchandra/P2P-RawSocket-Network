# Downloads chunks from multiple peers

import time
import queue
import socket
import threading
from typing import Dict, List, Optional
from protocol.constants import OP_CHUNK_REQ, OP_CHUNK_RESP, SOCKET_TIMEOUT
from protocol.packet import P2PPacket, read_packet, send_packet
from protocol.serializer import encode_chunk_req, decode_chunk_resp
from .chunker import FileManifest, verify_chunk, reassemble_file

class SwarmDownloader:
    def __init__(self, manifest: FileManifest, output_filepath: str, peer_addresses: List[tuple], max_workers: int = 4):
        self.manifest = manifest
        self.output_filepath = output_filepath
        self.peer_addresses = peer_addresses
        self.max_workers = min(max_workers, len(peer_addresses) * 2, manifest.chunk_count)
        self.chunk_queue = queue.Queue()
        for idx in range(manifest.chunk_count):
            self.chunk_queue.put(idx)
        self.received_chunks = {}
        self.chunks_lock = threading.Lock()
        self.is_cancelled = False

# Main PeerNode class: runs a TCP server to respond to chunk requests
# and a client to download files from other peers.

import os
import uuid
import socket
import select
import threading
from typing import Dict, List, Optional, Callable, Any

from protocol.constants import (
    DEFAULT_TCP_PORT,
    DEFAULT_UDP_PORT,
    SOCKET_TIMEOUT,
    OP_HANDSHAKE,
    OP_HANDSHAKE_ACK,
    OP_PING,
    OP_PONG,
    OP_FILE_LIST_REQ,
    OP_FILE_LIST_RESP,
    OP_FILE_META_REQ,
    OP_FILE_META_RESP,
    OP_CHUNK_REQ,
    OP_CHUNK_RESP,
    OP_ERROR,
)
from protocol.packet import P2PPacket, read_packet, send_packet, ConnectionClosedError, InvalidPacketError
from protocol.serializer import (
    encode_handshake,
    decode_handshake,
    encode_file_list,
    decode_file_list,
    encode_file_meta_req,
    decode_file_meta_req,
    encode_file_meta_resp,
    decode_file_meta_resp,
    encode_chunk_req,
    decode_chunk_req,
    encode_chunk_resp,
    decode_chunk_resp,
    encode_json_payload,
)
from core.chunker import FileManifest
from core.file_manager import FileManager
from core.peer_discovery import UDPPeerDiscovery, PeerInfo
from core.transfer_engine import SwarmDownloader


class PeerNode:
    # A single peer in the network. Can share files and download from others.

    def __init__(
        self,
        node_id: Optional[str] = None,
        bind_ip: str = "0.0.0.0",
        tcp_port: int = DEFAULT_TCP_PORT,
        udp_port: int = DEFAULT_UDP_PORT,
        storage_dir: str = "./shared_storage",
        download_dir: str = "./downloads",
        enable_discovery: bool = True,
    ):
        self.node_id = node_id or f"node_{uuid.uuid4().hex[:8]}"
        self.bind_ip = bind_ip
        self.tcp_port = tcp_port
        self.udp_port = udp_port

        self.file_manager = FileManager(storage_dir, download_dir)
        self.enable_discovery = enable_discovery

        # Always initialize discovery peer table for manual/broadcast tracking
        self.discovery = UDPPeerDiscovery(
            node_id=self.node_id,
            tcp_port=self.tcp_port,
            udp_port=self.udp_port,
            get_shared_count_cb=lambda: len(self.file_manager.files),
        )

        self._server_socket: Optional[socket.socket] = None
        self._running = False
        self._server_thread: Optional[threading.Thread] = None
        self._active_connections: List[socket.socket] = []
        self._connections_lock = threading.Lock()

        # Event callbacks for UI
        self.on_log: Optional[Callable[[str], None]] = None

    def add_peer(self, ip: str, tcp_port: int, node_id: Optional[str] = None) -> PeerInfo:
        """Helper to add peer directly to routing table."""
        return self.discovery.add_peer_manually(ip, tcp_port, node_id)

    def log(self, message: str):
        """Dispatches log events to UI or standard output."""
        formatted = f"[{self.node_id[:8]}] {message}"
        if self.on_log:
            self.on_log(formatted)
        else:
            print(formatted)

    def start(self):
        """Binds TCP listener socket and starts discovery service."""
        self._running = True

        # Initialize TCP Server socket
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.bind_ip, self.tcp_port))
        self._server_socket.listen(15)
        self._server_socket.settimeout(1.0)

        # Retrieve actual assigned port (in case tcp_port was 0)
        self.tcp_port = self._server_socket.getsockname()[1]
        self.discovery.tcp_port = self.tcp_port
        self.log(f"Listening for connections on {self.bind_ip}:{self.tcp_port}")

        self._server_thread = threading.Thread(
            target=self._server_accept_loop,
            name=f"TCP-Server-{self.node_id[:6]}",
            daemon=True,
        )
        self._server_thread.start()

        # Start UDP Discovery if enabled
        if self.enable_discovery:
            self.discovery.start()
            self.log(f"Discovery beacon active on UDP port {self.udp_port}")

    def stop(self):
        """Stops listener, discovery, and closes connections."""
        self._running = False
        if self.discovery:
            self.discovery.stop()

        with self._connections_lock:
            for s in self._active_connections:
                try:
                    s.close()
                except Exception:
                    pass
            self._active_connections.clear()

        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass

        self.log("Node stopped successfully.")

    def _server_accept_loop(self):
        """Background thread accepting inbound peer socket connections."""
        while self._running:
            try:
                conn, addr = self._server_socket.accept()
                with self._connections_lock:
                    self._active_connections.append(conn)

                handler = threading.Thread(
                    target=self._handle_client_connection,
                    args=(conn, addr),
                    name=f"PeerHandler-{addr[0]}:{addr[1]}",
                    daemon=True,
                )
                handler.start()
            except socket.timeout:
                continue
            except Exception:
                if self._running:
                    continue
                break

    def _handle_client_connection(self, conn: socket.socket, addr: tuple):
        """Handles sequential packet exchanges over an established peer socket."""
        conn.settimeout(15.0)
        try:
            while self._running:
                try:
                    packet = read_packet(conn)
                except (ConnectionClosedError, TimeoutError, socket.timeout):
                    break
                except InvalidPacketError as e:
                    self.log(f"Protocol error from {addr}: {e}")
                    break

                # Dispatch based on OpCode
                if packet.msg_type == OP_HANDSHAKE:
                    info = decode_handshake(packet.payload)
                    resp = P2PPacket(
                        msg_type=OP_HANDSHAKE_ACK,
                        payload=encode_handshake(self.node_id, self.tcp_port),
                        seq_num=packet.seq_num,
                    )
                    send_packet(conn, resp)

                elif packet.msg_type == OP_PING:
                    resp = P2PPacket(msg_type=OP_PONG, seq_num=packet.seq_num)
                    send_packet(conn, resp)

                elif packet.msg_type == OP_FILE_LIST_REQ:
                    files = self.file_manager.list_shared_files()
                    resp = P2PPacket(
                        msg_type=OP_FILE_LIST_RESP,
                        payload=encode_file_list(files),
                        seq_num=packet.seq_num,
                    )
                    send_packet(conn, resp)

                elif packet.msg_type == OP_FILE_META_REQ:
                    file_id = decode_file_meta_req(packet.payload)
                    manifest = self.file_manager.get_manifest(file_id)
                    if manifest:
                        resp = P2PPacket(
                            msg_type=OP_FILE_META_RESP,
                            payload=encode_file_meta_resp(manifest.to_dict()),
                            seq_num=packet.seq_num,
                        )
                    else:
                        resp = P2PPacket(
                            msg_type=OP_ERROR,
                            payload=encode_json_payload({"error": "File not found"}),
                            seq_num=packet.seq_num,
                        )
                    send_packet(conn, resp)

                elif packet.msg_type == OP_CHUNK_REQ:
                    file_id, chunk_index = decode_chunk_req(packet.payload)
                    chunk_data = self.file_manager.get_chunk(file_id, chunk_index)
                    if chunk_data is not None:
                        resp = P2PPacket(
                            msg_type=OP_CHUNK_RESP,
                            payload=encode_chunk_resp(file_id, chunk_index, chunk_data),
                            seq_num=packet.seq_num,
                        )
                    else:
                        resp = P2PPacket(
                            msg_type=OP_ERROR,
                            payload=encode_json_payload({"error": f"Chunk {chunk_index} not found"}),
                            seq_num=packet.seq_num,
                        )
                    send_packet(conn, resp)

        except Exception as e:
            self.log(f"Connection handler exception with {addr}: {e}")
        finally:
            with self._connections_lock:
                if conn in self._active_connections:
                    self._active_connections.remove(conn)
            try:
                conn.close()
            except Exception:
                pass

    # --- Client Interaction Methods ---

    def query_peer_files(self, peer_ip: str, peer_port: int) -> List[Dict[str, Any]]:
        """Queries a peer node for its list of available files."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(SOCKET_TIMEOUT)
        try:
            s.connect((peer_ip, peer_port))
            # Send file list request
            req = P2PPacket(msg_type=OP_FILE_LIST_REQ, seq_num=1)
            send_packet(s, req)

            resp = read_packet(s)
            if resp.msg_type == OP_FILE_LIST_RESP:
                return decode_file_list(resp.payload)
            return []
        finally:
            s.close()

    def fetch_manifest(self, peer_ip: str, peer_port: int, file_id: str) -> Optional[FileManifest]:
        """Fetches file metadata manifest and piece hashes from a peer."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(SOCKET_TIMEOUT)
        try:
            s.connect((peer_ip, peer_port))
            req = P2PPacket(
                msg_type=OP_FILE_META_REQ,
                payload=encode_file_meta_req(file_id),
                seq_num=2,
            )
            send_packet(s, req)

            resp = read_packet(s)
            if resp.msg_type == OP_FILE_META_RESP:
                data = decode_file_meta_resp(resp.payload)
                return FileManifest.from_dict(data)
            return None
        finally:
            s.close()

    def download_file(
        self,
        file_id: str,
        custom_save_name: Optional[str] = None,
        progress_cb: Optional[Callable[[int, int, float], None]] = None,
    ) -> str:
        """
        Orchestrates full swarm download:
        1. Identifies all known peers seeding the file
        2. Retrieves manifest
        3. Downloads chunks across multiple peers in parallel
        4. Reassembles and verifies integrity
        5. Registers newly downloaded file into local storage to seed it!
        """
        active_peers = self.discovery.get_active_peers() if self.discovery else []
        if not active_peers:
            raise RuntimeError("No active peers found in network.")

        # Find peers that host this file
        seeders: List[tuple[str, int]] = []
        target_manifest = None

        for p in active_peers:
            try:
                files = self.query_peer_files(p.ip, p.tcp_port)
                for f in files:
                    if f["file_id"] == file_id:
                        seeders.append((p.ip, p.tcp_port))
                        if target_manifest is None:
                            target_manifest = self.fetch_manifest(p.ip, p.tcp_port, file_id)
                        break
            except Exception:
                continue

        if not seeders or target_manifest is None:
            raise RuntimeError(f"File ID {file_id} could not be located on any active peer.")

        save_name = custom_save_name or target_manifest.file_name
        dest_path = os.path.join(self.file_manager.download_dir, save_name)

        self.log(
            f"Starting swarm download of '{target_manifest.file_name}' ({target_manifest.file_size} bytes) "
            f"from {len(seeders)} seeders across {target_manifest.chunk_count} chunks..."
        )

        downloader = SwarmDownloader(
            manifest=target_manifest,
            output_filepath=dest_path,
            peer_addresses=seeders,
            max_workers=4,
            progress_cb=progress_cb,
        )

        downloader.start_download()

        # Seed the newly completed file
        self.file_manager.mark_download_complete(file_id, dest_path, target_manifest)
        self.log(f"Download complete! File saved and verified: {dest_path}")
        return dest_path

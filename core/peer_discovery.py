# Local network peer discovery using UDP broadcast packets.
# Each peer broadcasts its IP and TCP port every few seconds.

import json
import time
import socket
import threading
from typing import Dict, Any, List, Optional
from protocol.constants import DEFAULT_UDP_PORT, BROADCAST_INTERVAL, PEER_TIMEOUT_SEC


class PeerInfo:
    def __init__(self, node_id: str, ip: str, tcp_port: int, last_seen: float, shared_count: int = 0):
        self.node_id = node_id
        self.ip = ip
        self.tcp_port = tcp_port
        self.last_seen = last_seen
        self.shared_count = shared_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "ip": self.ip,
            "tcp_port": self.tcp_port,
            "last_seen": self.last_seen,
            "shared_count": self.shared_count,
        }

    def __repr__(self) -> str:
        return f"<Peer {self.node_id[:8]}@{self.ip}:{self.tcp_port}>"


class UDPPeerDiscovery:
    def __init__(
        self,
        node_id: str,
        tcp_port: int,
        udp_port: int = DEFAULT_UDP_PORT,
        get_shared_count_cb=None,
    ):
        self.node_id = node_id
        self.tcp_port = tcp_port
        self.udp_port = udp_port
        self.get_shared_count_cb = get_shared_count_cb

        self.known_peers: Dict[str, PeerInfo] = {}
        self.peers_lock = threading.Lock()

        self._running = False
        self._listener_thread: Optional[threading.Thread] = None
        self._beacon_thread: Optional[threading.Thread] = None
        self._cleanup_thread: Optional[threading.Thread] = None

    def start(self):
        self._running = True

        self._listener_thread = threading.Thread(
            target=self._listen_loop, name=f"UDP-Listen-{self.node_id[:6]}", daemon=True
        )
        self._beacon_thread = threading.Thread(
            target=self._beacon_loop, name=f"UDP-Beacon-{self.node_id[:6]}", daemon=True
        )
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop, name=f"UDP-Clean-{self.node_id[:6]}", daemon=True
        )

        self._listener_thread.start()
        self._beacon_thread.start()
        self._cleanup_thread.start()

    def stop(self):
        self._running = False

    def add_peer_manually(self, ip: str, tcp_port: int, node_id: Optional[str] = None) -> PeerInfo:
        # Useful for testing locally or if UDP broadcast is blocked by firewall
        if not node_id:
            node_id = f"peer_{ip}_{tcp_port}"

        with self.peers_lock:
            info = PeerInfo(
                node_id=node_id,
                ip=ip,
                tcp_port=tcp_port,
                last_seen=time.time(),
                shared_count=0,
            )
            self.known_peers[node_id] = info
            return info

    def get_active_peers(self) -> List[PeerInfo]:
        with self.peers_lock:
            return list(self.known_peers.values())

    def _listen_loop(self):
        # Listens for UDP beacon broadcasts from other peers on the LAN
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.bind(("", self.udp_port))
            sock.settimeout(1.0)
        except Exception:
            sock.close()
            return

        while self._running:
            try:
                data, addr = sock.recvfrom(2048)
                payload = json.loads(data.decode("utf-8"))

                remote_node_id = payload.get("node_id")
                remote_tcp_port = payload.get("tcp_port")
                shared_count = payload.get("shared_count", 0)

                # Skip our own broadcast
                if remote_node_id and remote_node_id != self.node_id:
                    remote_ip = addr[0]
                    if remote_ip == "0.0.0.0":
                        remote_ip = "127.0.0.1"

                    with self.peers_lock:
                        self.known_peers[remote_node_id] = PeerInfo(
                            node_id=remote_node_id,
                            ip=remote_ip,
                            tcp_port=remote_tcp_port,
                            last_seen=time.time(),
                            shared_count=shared_count,
                        )
            except (socket.timeout, BlockingIOError):
                continue
            except Exception:
                continue

        try:
            sock.close()
        except Exception:
            pass

    def _beacon_loop(self):
        # Sends a heartbeat message over UDP broadcast every few seconds
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except Exception:
            pass

        while self._running:
            try:
                shared_count = self.get_shared_count_cb() if self.get_shared_count_cb else 0
                beacon_data = {
                    "node_id": self.node_id,
                    "tcp_port": self.tcp_port,
                    "shared_count": shared_count,
                    "timestamp": time.time(),
                }
                msg = json.dumps(beacon_data).encode("utf-8")

                for target_ip in ["<broadcast>", "255.255.255.255", "127.0.0.1"]:
                    try:
                        sock.sendto(msg, (target_ip, self.udp_port))
                    except Exception:
                        pass
            except Exception:
                pass

            time.sleep(BROADCAST_INTERVAL)

        try:
            sock.close()
        except Exception:
            pass


# Local network peer discovery using UDP broadcast packets

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

    def __repr__(self):
        return f"<Peer {self.node_id[:8]}@{self.ip}:{self.tcp_port}>"

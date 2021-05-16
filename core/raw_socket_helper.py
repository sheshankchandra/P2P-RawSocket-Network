# A small experimental packet sniffer.
# Uses Scapy (or raw sockets) to inspect IP/TCP packets on the wire.
# Note: On Windows/Linux, capturing raw packets requires running as Administrator/root.

import logging
import socket
import struct
from typing import Dict, Any
from protocol.constants import MAGIC_BYTES

# Suppress scapy's libpcap warning on Windows
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)

try:
    from scapy.layers.inet import IP, TCP
    from scapy.packet import Raw
    USE_SCAPY = True
except ImportError:
    USE_SCAPY = False


def parse_packet_with_scapy(raw_data: bytes) -> Dict[str, Any]:
    # Dissects raw packet bytes using Scapy
    pkt = IP(raw_data)
    info = {
        "src_ip": pkt.src,
        "dst_ip": pkt.dst,
        "ttl": pkt.ttl,
        "protocol": pkt.proto,
        "total_length": pkt.len,
        "tcp": None,
        "has_p2p_magic": False,
    }

    if pkt.haslayer(TCP):
        tcp_layer = pkt[TCP]
        info["tcp"] = {
            "src_port": tcp_layer.sport,
            "dst_port": tcp_layer.dport,
            "seq_num": tcp_layer.seq,
            "ack_num": tcp_layer.ack,
            "flags": str(tcp_layer.flags),
            "window": tcp_layer.window,
        }

    if pkt.haslayer(Raw):
        raw_payload = bytes(pkt[Raw])
        if MAGIC_BYTES in raw_payload:
            info["has_p2p_magic"] = True

    return info


def parse_ipv4_header_fallback(raw_data: bytes) -> Dict[str, Any]:
    # Fallback manual header parser if Scapy is not available
    if len(raw_data) < 20:
        raise ValueError("Packet data too short for IPv4 header")

    ip_header = raw_data[:20]
    iph = struct.unpack("!BBHHHBBH4s4s", ip_header)
    version_ihl = iph[0]
    ihl = (version_ihl & 0xF) * 4

    return {
        "version": version_ihl >> 4,
        "ihl": ihl,
        "tos": iph[1],
        "total_length": iph[2],
        "identification": iph[3],
        "flags_fragment": iph[4],
        "ttl": iph[5],
        "protocol": iph[6],
        "checksum": iph[7],
        "src_ip": socket.inet_ntoa(iph[8]),
        "dst_ip": socket.inet_ntoa(iph[9]),
    }


def start_raw_packet_sniffer(host_ip: str = "127.0.0.1", count: int = 5):
    try:
        sniffer = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)
        sniffer.bind((host_ip, 0))
        sniffer.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)

        if hasattr(socket, "SIO_RCVALL"):
            sniffer.ioctl(socket.SIO_RCVALL, socket.RCVALL_ON)

        print(f"\n[Sniffer] Listening on {host_ip} for {count} packets...")

        captured = 0
        while captured < count:
            raw_buffer, addr = sniffer.recvfrom(65535)
            captured += 1

            if USE_SCAPY:
                try:
                    info = parse_packet_with_scapy(raw_buffer)
                    print(f"\n--- [Packet #{captured}] ---")
                    print(f"IP:  {info['src_ip']} -> {info['dst_ip']} | Proto: {info['protocol']} | TTL: {info['ttl']}")
                    if info["tcp"]:
                        tcp = info["tcp"]
                        print(f"TCP: {tcp['src_port']} -> {tcp['dst_port']} | Flags: [{tcp['flags']}]")
                    if info["has_p2p_magic"]:
                        print("     * Found P2PF packet!")
                    continue
                except Exception:
                    pass

            ip_info = parse_ipv4_header_fallback(raw_buffer)
            print(f"\n--- [Packet #{captured}] ---")
            print(f"IP: {ip_info['src_ip']} -> {ip_info['dst_ip']} | Proto: {ip_info['protocol']}")

        if hasattr(socket, "SIO_RCVALL"):
            sniffer.ioctl(socket.SIO_RCVALL, socket.RCVALL_OFF)
        sniffer.close()

    except PermissionError:
        print("[Sniffer] Note: Need Administrator privileges to open raw sockets on Windows.")
    except Exception as e:
        print(f"[Sniffer] Error: {e}")


parse_ipv4_header = parse_ipv4_header_fallback


def parse_tcp_header(raw_data: bytes) -> Dict[str, Any]:
    if USE_SCAPY:
        try:
            tcp = TCP(raw_data)
            return {
                "src_port": tcp.sport,
                "dst_port": tcp.dport,
                "seq_num": tcp.seq,
                "ack_num": tcp.ack,
                "flags": str(tcp.flags),
                "window": tcp.window,
            }
        except Exception:
            pass

    tcph = struct.unpack("!HHLLBBHHH", raw_data[:20])
    return {
        "src_port": tcph[0],
        "dst_port": tcph[1],
        "seq_num": tcph[2],
        "ack_num": tcph[3],
        "flags": str(tcph[5]),
        "window": tcph[6],
    }

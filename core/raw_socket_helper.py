# A small experimental packet sniffer.
# Uses raw sockets to inspect IP packets on the wire.

import socket
import struct
from typing import Dict, Any

def parse_ipv4_header_fallback(raw_data: bytes) -> Dict[str, Any]:
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

parse_ipv4_header = parse_ipv4_header_fallback

def start_raw_packet_sniffer(host_ip: str = "127.0.0.1", count: int = 5):
    try:
        sniffer = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)
        sniffer.bind((host_ip, 0))
        sniffer.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
        if hasattr(socket, "SIO_RCVALL"):
            sniffer.ioctl(socket.SIO_RCVALL, socket.RCVALL_ON)
        print(f"\n[Sniffer] Listening on {host_ip} for {count} packets...")
        for _ in range(count):
            raw_buffer, addr = sniffer.recvfrom(65535)
            ip_info = parse_ipv4_header(raw_buffer)
            print(f"IP: {ip_info['src_ip']} -> {ip_info['dst_ip']} | Proto: {ip_info['protocol']}")
        if hasattr(socket, "SIO_RCVALL"):
            sniffer.ioctl(socket.SIO_RCVALL, socket.RCVALL_OFF)
        sniffer.close()
    except Exception as e:
        print(f"[Sniffer] Error: {e}")

def parse_tcp_header(raw_data: bytes) -> Dict[str, Any]:
    tcph = struct.unpack("!HHLLBBHHH", raw_data[:20])
    return {
        "src_port": tcph[0],
        "dst_port": tcph[1],
        "seq_num": tcph[2],
        "ack_num": tcph[3],
        "flags": str(tcph[5]),
        "window": tcph[6],
    }

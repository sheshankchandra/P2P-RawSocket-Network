# Multi-node simulation test: runs 3 nodes locally (Alice, Bob, Charlie)
# and tests parallel chunk downloading and hash checks.

import os
import time
import shutil
import hashlib
from node.peer_node import PeerNode
from protocol.constants import DEFAULT_CHUNK_SIZE
from protocol.packet import P2PPacket, InvalidPacketError
from protocol.constants import OP_PING

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    USE_RICH = True
    console = Console()
except ImportError:
    USE_RICH = False
    console = None


def generate_test_file(filepath: str, size_bytes: int) -> str:
    # Creates dummy binary test data
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    pattern = b"P2P_FILE_SHARE_TEST_DATA_BLOCK!" * 64
    with open(filepath, "wb") as f:
        written = 0
        while written < size_bytes:
            to_write = min(len(pattern), size_bytes - written)
            f.write(pattern[:to_write])
            written += to_write

    with open(filepath, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def log_step(step_num: int, title: str):
    if USE_RICH:
        console.print(f"\n[bold cyan]Step {step_num}:[/] [bold white]{title}[/]")
    else:
        print(f"\n[Step {step_num}] {title}")


def log_success(message: str):
    if USE_RICH:
        console.print(f"  [bold green][PASS][/] {message}")
    else:
        print(f"  [PASSED] {message}")


def run_simulation():
    if USE_RICH:
        console.print(Panel(
            "[bold white]Testing multi-peer chunk downloads, bitfield tracking, and packet verification.[/]",
            title="[bold cyan]P2P Swarm Simulation[/]",
            border_style="cyan",
        ))
    else:
        print("=" * 60)
        print("  P2P Swarm Simulation Test")
        print("=" * 60)

    test_dir = os.path.abspath("./test_workspace")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir, exist_ok=True)

    alice_storage = os.path.join(test_dir, "alice_storage")
    alice_downloads = os.path.join(test_dir, "alice_downloads")
    bob_storage = os.path.join(test_dir, "bob_storage")
    bob_downloads = os.path.join(test_dir, "bob_downloads")
    charlie_storage = os.path.join(test_dir, "charlie_storage")
    charlie_downloads = os.path.join(test_dir, "charlie_downloads")

    # 1. Create a 200 KB test file (spans ~4 chunks of 64KB)
    sample_file_path = os.path.join(alice_storage, "sample_document.pdf")
    original_sha256 = generate_test_file(sample_file_path, 200 * 1024)
    log_step(1, "Created test file")
    print(f"         Path:   {sample_file_path}")
    print(f"         Size:   204,800 bytes")
    print(f"         SHA256: {original_sha256}")

    # 2. Launch 3 Peer Nodes with unique ports
    log_step(2, "Starting 3 local nodes (Alice: 7001, Bob: 7002, Charlie: 7003)")
    alice = PeerNode("Alice", bind_ip="127.0.0.1", tcp_port=7001, storage_dir=alice_storage, download_dir=alice_downloads, enable_discovery=False)
    bob = PeerNode("Bob", bind_ip="127.0.0.1", tcp_port=7002, storage_dir=bob_storage, download_dir=bob_downloads, enable_discovery=False)
    charlie = PeerNode("Charlie", bind_ip="127.0.0.1", tcp_port=7003, storage_dir=charlie_storage, download_dir=charlie_downloads, enable_discovery=False)

    alice.start()
    bob.start()
    charlie.start()
    time.sleep(0.5)

    try:
        # 3. Alice seeds the file
        log_step(3, "Alice indexes file into 64KB pieces and creates bitfield")
        manifest = alice.file_manager.add_file(sample_file_path)
        bitfield = alice.file_manager.get_bitfield(manifest.file_id)
        assert manifest.chunk_count == 4, f"Expected 4 chunks, got {manifest.chunk_count}"
        assert manifest.file_id == original_sha256, "Manifest file ID matches original SHA256"
        assert bitfield.is_complete(), "Alice's bitfield should have all pieces"
        log_success(f"Alice indexed {manifest.chunk_count} chunks: {bitfield}")

        # 4. Bob connects to Alice and downloads the file
        log_step(4, "Bob connects to Alice (127.0.0.1:7001) and downloads")
        bob.add_peer("127.0.0.1", 7001, node_id="Alice")
        bob_received_file = bob.download_file(file_id=manifest.file_id)

        with open(bob_received_file, "rb") as f:
            bob_sha256 = hashlib.sha256(f.read()).hexdigest()
        assert bob_sha256 == original_sha256, "Bob's file matches Alice's original"
        log_success(f"Bob downloaded and verified SHA-256: {bob_sha256[:16]}...")

        # 5. Charlie connects to both Alice and Bob
        log_step(5, "Charlie connects to both Alice (7001) and Bob (7002)")
        charlie.add_peer("127.0.0.1", 7001, node_id="Alice")
        charlie.add_peer("127.0.0.1", 7002, node_id="Bob")

        # 6. Charlie downloads chunks in parallel from both seeders
        log_step(6, "Charlie downloads pieces in parallel from Alice and Bob")
        progress_records = []
        def on_charlie_progress(done, total, speed):
            progress_records.append((done, total, speed))
            print(f"         Transfer: {done}/{total} chunks | {speed:.1f} KB/s")

        charlie_received_file = charlie.download_file(
            file_id=manifest.file_id,
            progress_cb=on_charlie_progress,
        )

        with open(charlie_received_file, "rb") as f:
            charlie_sha256 = hashlib.sha256(f.read()).hexdigest()
        assert charlie_sha256 == original_sha256, "Charlie's file matches original"
        log_success(f"Charlie downloaded and verified SHA-256: {charlie_sha256[:16]}...")

        # 7. Test Packet Checksum / Corrupted Frame Rejection
        log_step(7, "Testing tamper detection with a bad CRC32 checksum")
        valid_packet = P2PPacket(msg_type=OP_PING, payload=b"PING_PAYLOAD", seq_num=99)
        raw_bytes = bytearray(valid_packet.to_bytes())
        
        # Corrupt 1 byte in payload
        raw_bytes[-1] ^= 0xFF

        tamper_detected = False
        try:
            from protocol.constants import HEADER_SIZE
            from protocol.packet import P2PHeaderConstruct, USE_CONSTRUCT
            if USE_CONSTRUCT:
                parsed = P2PHeaderConstruct.parse(raw_bytes[:HEADER_SIZE])
                P2PPacket.from_header_and_payload(
                    b"P2PF", parsed.version, parsed.msg_type, parsed.flags,
                    parsed.seq_num, parsed.payload_len, parsed.checksum, raw_bytes[HEADER_SIZE:]
                )
        except InvalidPacketError as err:
            tamper_detected = True
            log_success(f"Corrupted packet caught by CRC-32 check: {err}")

        assert tamper_detected, "Integrity check must fail on corrupted packet"

        if USE_RICH:
            summary = Table(title="Simulation Test Summary", border_style="green")
            summary.add_column("Check", style="white")
            summary.add_column("Result", style="bold green")
            summary.add_column("Component", style="cyan")
            summary.add_row("Chunking & Bitfield", "PASS", "bitarray + hashlib")
            summary.add_row("Binary Framing", "PASS", "construct (20-byte header)")
            summary.add_row("Single-Peer Download (Bob)", "PASS", "TCP sockets")
            summary.add_row("Multi-Peer Parallel Download (Charlie)", "PASS", "Worker threads")
            summary.add_row("Tampered Packet Rejection", "PASS", "CRC-32 checksum")
            console.print(summary)
        else:
            print("\n" + "=" * 60)
            print("  All simulation tests passed.")
            print("=" * 60)

    finally:
        print("\nStopping test nodes...")
        alice.stop()
        bob.stop()
        charlie.stop()
        try:
            shutil.rmtree(test_dir)
        except Exception:
            pass


if __name__ == "__main__":
    run_simulation()

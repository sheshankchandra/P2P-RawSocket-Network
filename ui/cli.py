# Interactive terminal interface for the P2P node.
# Uses 'rich' for clean tables and progress bars if installed.

import os
import sys
import time
from typing import Optional, List
from node.peer_node import PeerNode
from core.raw_socket_helper import start_raw_packet_sniffer

# Load rich for terminal styling
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.progress import (
        Progress,
        SpinnerColumn,
        TextColumn,
        BarColumn,
        TaskProgressColumn,
        TimeRemainingColumn,
    )
    USE_RICH = True
    console = Console()
except ImportError:
    USE_RICH = False
    console = None


def format_bytes(num_bytes: int) -> str:
    """Human readable byte size formatter."""
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} TB"


def print_banner(node_id: str, tcp_port: int, udp_port: int):
    if USE_RICH:
        content = (
            f"[bold green]Node ID:[/]   [cyan]{node_id}[/]\n"
            f"[bold green]TCP Port:[/]  [white]0.0.0.0:{tcp_port}[/]\n"
            f"[bold green]UDP Port:[/]  [white]{udp_port}[/] (peer discovery)\n\n"
            f"[dim]Type 'help' for commands, or 'exit' to quit.[/]"
        )
        panel = Panel(
            content,
            title="[bold cyan]P2P File Sharing[/]",
            border_style="cyan",
            expand=False,
        )
        console.print(panel)
    else:
        print(f"""
--------------------------------------------------
  P2P File Sharing
--------------------------------------------------
  Node ID   : {node_id}
  TCP Port  : 0.0.0.0:{tcp_port}
  UDP Port  : {udp_port}
  Type 'help' for commands.
--------------------------------------------------
""")


class CLIApp:
    """Command line manager for interacting with a PeerNode."""

    def __init__(self, node: PeerNode):
        self.node = node

    def run(self):
        print_banner(self.node.node_id, self.node.tcp_port, self.node.udp_port)

        while True:
            try:
                prompt_str = f"({self.node.node_id[:8]})> "
                raw_input = input(f"\n{prompt_str}").strip()
                if not raw_input:
                    continue

                parts = raw_input.split()
                cmd = parts[0].lower()
                args = parts[1:]

                if cmd in ("exit", "quit", "q"):
                    if USE_RICH:
                        console.print("[yellow]Stopping node and closing sockets...[/]")
                    else:
                        print("Shutting down node...")
                    self.node.stop()
                    break

                elif cmd == "help":
                    self.cmd_help()

                elif cmd == "peers":
                    self.cmd_peers()

                elif cmd == "addpeer":
                    self.cmd_addpeer(args)

                elif cmd == "share":
                    self.cmd_share(args)

                elif cmd == "myfiles":
                    self.cmd_myfiles()

                elif cmd == "networkfiles":
                    self.cmd_networkfiles()

                elif cmd == "search":
                    self.cmd_search(args)

                elif cmd == "download":
                    self.cmd_download(args)

                elif cmd == "sniff":
                    self.cmd_sniff(args)

                else:
                    if USE_RICH:
                        console.print(f"[red]Unknown command: '{cmd}'. Type [bold white]'help'[/] for reference.[/]")
                    else:
                        print(f"Unknown command: '{cmd}'. Type 'help' for available commands.")

            except (KeyboardInterrupt, EOFError):
                print("\nInterrupted. Exiting...")
                self.node.stop()
                break
            except Exception as e:
                if USE_RICH:
                    console.print(f"[bold red][Error][/] {e}")
                else:
                    print(f"[Error] {e}")

    def cmd_help(self):
        if USE_RICH:
            table = Table(title="P2P Network Commands Reference", border_style="dim")
            table.add_column("Command", style="bold cyan", width=22)
            table.add_column("Description", style="white")
            table.add_row("peers", "List all discovered active peers in LAN / swarm")
            table.add_row("addpeer <ip> <port>", "Manually connect to a peer by TCP port")
            table.add_row("share <filepath>", "Index and seed a local file into 64 KB pieces")
            table.add_row("myfiles", "View files currently seeded by this node with Bitfield")
            table.add_row("networkfiles", "Discover files available across all remote peers")
            table.add_row("search <keyword>", "Search files by name across the swarm")
            table.add_row("download <file_id>", "Swarm download a file using multi-peer parallel chunks")
            table.add_row("sniff [count]", "Run Layer 3/4 Raw Socket Sniffer (Scapy / Admin)")
            table.add_row("help", "Show this command reference")
            table.add_row("exit / quit", "Stop node and exit")
            console.print(table)
        else:
            print("""
Available Commands:
  peers                       - List all discovered active peers in LAN/swarm
  addpeer <ip> <port>         - Manually add a peer by IP and TCP port
  share <file_path>           - Index and share a local file with the network
  myfiles                     - View files currently seeded by this node
  networkfiles                - Discover files available across all remote peers
  search <keyword>            - Search files by name across the network
  download <file_id> [name]   - Swarm download a file using multi-peer chunks
  sniff [count]               - Run Layer 3/4 Raw Socket Sniffer (requires Admin)
  help                        - Show this command reference
  exit / quit                 - Stop node and exit
""")

    def cmd_peers(self):
        peers = self.node.discovery.get_active_peers() if self.node.discovery else []
        if not peers:
            if USE_RICH:
                console.print("[dim yellow]No active peers discovered yet. (Peers broadcast beacons every 3s)[/]")
            else:
                print("No active peers discovered yet. (Peers broadcast beacons every 3s)")
            return

        if USE_RICH:
            table = Table(title=f"Active Network Peers ({len(peers)})", border_style="cyan")
            table.add_column("Node ID", style="bold cyan")
            table.add_column("Socket Address", style="bold green")
            table.add_column("Last Seen", style="magenta")
            table.add_column("Shared Files", justify="right", style="yellow")

            now = time.time()
            for p in peers:
                ago = now - p.last_seen
                table.add_row(p.node_id, f"{p.ip}:{p.tcp_port}", f"{ago:.1f}s ago", str(p.shared_count))
            console.print(table)
        else:
            print(f"\n--- Discovered Peers ({len(peers)}) ---")
            for idx, p in enumerate(peers, 1):
                ago = time.time() - p.last_seen
                print(f" {idx}. Node: {p.node_id[:12]} | Address: {p.ip}:{p.tcp_port} | Last Seen: {ago:.1f}s ago | Shared: {p.shared_count} files")

    def cmd_addpeer(self, args):
        if len(args) < 2:
            print("Usage: addpeer <ip> <tcp_port>")
            return
        ip = args[0]
        port = int(args[1])
        self.node.add_peer(ip, port)
        if USE_RICH:
            console.print(f"[bold green][+][/] Added peer [cyan]{ip}:{port}[/] to routing table.")
        else:
            print(f"Added peer {ip}:{port} to known peer table.")

    def cmd_share(self, args):
        if not args:
            print("Usage: share <filepath>")
            return
        filepath = " ".join(args)
        if not os.path.isfile(filepath):
            print(f"Error: file not found: {filepath}")
            return

        manifest = self.node.file_manager.add_file(filepath)
        if USE_RICH:
            console.print(Panel(
                f"[bold white]File:[/]   {manifest.file_name}\n"
                f"[bold white]Size:[/]   {format_bytes(manifest.file_size)} ({manifest.file_size:,} bytes)\n"
                f"[bold white]Pieces:[/] {manifest.chunk_count} chunks @ {format_bytes(manifest.chunk_size)}\n"
                f"[bold white]SHA256:[/] [yellow]{manifest.file_id}[/]",
                title="[bold green]File Shared[/]",
                border_style="green",
            ))
        else:
            print(f"\n[+] Successfully shared file:")
            print(f"    Name:   {manifest.file_name}")
            print(f"    Size:   {manifest.file_size:,} bytes")
            print(f"    Chunks: {manifest.chunk_count} pieces")
            print(f"    FileID: {manifest.file_id}")

    def cmd_myfiles(self):
        files = self.node.file_manager.list_shared_files()
        if not files:
            if USE_RICH:
                console.print("[dim yellow]No files currently seeded. Use 'share <filepath>' to add one.[/]")
            else:
                print("No files currently seeded. Use 'share <filepath>' to share a file.")
            return

        if USE_RICH:
            table = Table(title="Locally Seeded Files", border_style="green")
            table.add_column("File Name", style="bold white")
            table.add_column("Size", justify="right", style="cyan")
            table.add_column("Chunks", justify="center", style="green")
            table.add_column("Status", justify="center", style="bold yellow")
            table.add_column("SHA-256 Digest", style="dim")

            for f in files:
                status = "Complete (100%)" if f.get("is_complete", True) else f"{f.get('completed_chunks', 0)}/{f['chunk_count']}"
                table.add_row(
                    f["file_name"],
                    format_bytes(f["file_size"]),
                    str(f["chunk_count"]),
                    status,
                    f["file_id"][:16] + "...",
                )
            console.print(table)
        else:
            print(f"\n--- Locally Seeded Files ({len(files)}) ---")
            for f in files:
                print(f" * {f['file_name']} | Size: {f['file_size']:,} B | Chunks: {f['chunk_count']} | ID: {f['file_id'][:16]}...")

    def cmd_networkfiles(self):
        peers = self.node.discovery.get_active_peers() if self.node.discovery else []
        if not peers:
            print("No peers connected to query.")
            return

        collected = []
        for p in peers:
            try:
                pfiles = self.node.query_peer_files(p.ip, p.tcp_port)
                for f in pfiles:
                    collected.append((f, p))
            except Exception:
                pass

        if not collected:
            if USE_RICH:
                console.print("[dim yellow]No files currently shared by active peers.[/]")
            else:
                print("No files currently shared by active peers.")
            return

        if USE_RICH:
            table = Table(title="Network Files Catalog", border_style="magenta")
            table.add_column("File Name", style="bold white")
            table.add_column("Size", justify="right", style="cyan")
            table.add_column("Chunks", justify="center", style="green")
            table.add_column("Seeder Node", style="yellow")
            table.add_column("File ID", style="dim")

            for f, p in collected:
                table.add_row(
                    f["file_name"],
                    format_bytes(f["file_size"]),
                    str(f["chunk_count"]),
                    f"{p.node_id[:8]} ({p.ip}:{p.tcp_port})",
                    f["file_id"],
                )
            console.print(table)
        else:
            print("\n--- Network Files Catalog ---")
            for f, p in collected:
                print(f" - [{f['file_name']}] Size: {f['file_size']:,} B | Chunks: {f['chunk_count']}")
                print(f"   Seeder: {p.node_id[:8]} ({p.ip}:{p.tcp_port}) | ID: {f['file_id']}")

    def cmd_search(self, args):
        if not args:
            print("Usage: search <keyword>")
            return
        keyword = " ".join(args).lower()
        peers = self.node.discovery.get_active_peers() if self.node.discovery else []

        results = []
        for p in peers:
            try:
                pfiles = self.node.query_peer_files(p.ip, p.tcp_port)
                for f in pfiles:
                    if keyword in f["file_name"].lower():
                        results.append((f, p))
            except Exception:
                pass

        if not results:
            if USE_RICH:
                console.print(f"[yellow]No files matching '{keyword}' found.[/]")
            else:
                print(f"No files matching '{keyword}' found.")
            return

        if USE_RICH:
            table = Table(title=f"Search Results for '{keyword}'", border_style="yellow")
            table.add_column("File Name", style="bold white")
            table.add_column("Size", justify="right", style="cyan")
            table.add_column("Seeder", style="green")
            table.add_column("File ID", style="dim")
            for f, p in results:
                table.add_row(f["file_name"], format_bytes(f["file_size"]), f"{p.ip}:{p.tcp_port}", f["file_id"])
            console.print(table)
        else:
            print(f"Found {len(results)} match(es):")
            for f, p in results:
                print(f" * {f['file_name']} ({f['file_size']:,} bytes) from {p.ip}:{p.tcp_port} | ID: {f['file_id']}")

    def cmd_download(self, args):
        if not args:
            print("Usage: download <file_id> [save_name]")
            return
        file_id = args[0]
        custom_name = args[1] if len(args) > 1 else None

        if USE_RICH:
            console.print(f"[cyan]Connecting to swarm for File ID:[/] [dim]{file_id}[/]")
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(complete_style="green", finished_style="bold green"),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("[green]Downloading chunks from swarm...", total=100)

                def on_progress(done, total, speed):
                    progress.update(
                        task,
                        completed=(done / total * 100.0) if total > 0 else 100.0,
                        description=f"[green]Downloading: {done}/{total} chunks @ {speed:.1f} KB/s",
                    )

                saved_to = self.node.download_file(
                    file_id=file_id,
                    custom_save_name=custom_name,
                    progress_cb=on_progress,
                )

            console.print(Panel(
                f"[bold green][OK] Swarm Download Completed & Verified![/]\n"
                f"[white]File saved to:[/] [cyan]{saved_to}[/]",
                border_style="green",
            ))
        else:
            def render_fallback_bar(completed: int, total: int, speed_kbs: float):
                percent = (completed / total) * 100.0 if total > 0 else 100.0
                sys.stdout.write(f"\r  Downloading: {percent:5.1f}% ({completed}/{total} chunks) | {speed_kbs:.2f} KB/s")
                sys.stdout.flush()
                if completed == total:
                    sys.stdout.write("\n")

            saved_to = self.node.download_file(
                file_id=file_id,
                custom_save_name=custom_name,
                progress_cb=render_fallback_bar,
            )
            print(f"\n[+] Success! File saved to: {saved_to}")

    def cmd_sniff(self, args):
        count = int(args[0]) if args else 5
        print(f"Running Raw Socket Sniffer for {count} packets...")
        start_raw_packet_sniffer(count=count)

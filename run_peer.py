# Entry point to launch a peer node.
# Examples:
#   python run_peer.py --id Alice --tcp 6001
#   python run_peer.py --id Bob --tcp 6002 --gui

import sys
import argparse
from node.peer_node import PeerNode
from ui.cli import CLIApp
from ui.gui import PeerNodeGUI


def main():
    parser = argparse.ArgumentParser(
        description="P2P File Sharing (Python socket project)"
    )
    parser.add_argument("--id", type=str, default=None, help="Custom identifier for this peer node")
    parser.add_argument("--tcp", type=int, default=6001, help="TCP port to listen on for incoming connections")
    parser.add_argument("--udp", type=int, default=9876, help="UDP port for LAN broadcast peer discovery")
    parser.add_argument("--bind", type=str, default="0.0.0.0", help="IP address to bind the server socket to")
    parser.add_argument("--storage", type=str, default=None, help="Directory path for shared/seeded files")
    parser.add_argument("--downloads", type=str, default=None, help="Directory path for completed downloads")
    parser.add_argument("--gui", action="store_true", help="Launch Tkinter desktop graphical interface")
    parser.add_argument("--no-discovery", action="store_true", help="Disable automatic UDP discovery beacons")

    args = parser.parse_args()

    node_id = args.id or f"node_{args.tcp}"
    storage_dir = args.storage or f"./storage_{node_id}"
    downloads_dir = args.downloads or f"./downloads_{node_id}"

    node = PeerNode(
        node_id=node_id,
        bind_ip=args.bind,
        tcp_port=args.tcp,
        udp_port=args.udp,
        storage_dir=storage_dir,
        download_dir=downloads_dir,
        enable_discovery=not args.no_discovery,
    )

    # Start network server
    node.start()

    if args.gui:
        app = PeerNodeGUI(node)
        app.start()
    else:
        app = CLIApp(node)
        app.run()


if __name__ == "__main__":
    main()

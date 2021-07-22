# Tkinter desktop interface for browsing and downloading files.

import os
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional, Dict, Any, List

from node.peer_node import PeerNode


class PeerNodeGUI:
    def __init__(self, node: PeerNode):
        self.node = node
        self.root = tk.Tk()
        self.root.title(f"P2P File Sharing - {self.node.node_id}")
        self.root.geometry("880x620")
        self.root.minsize(780, 520)

        # Connect logging callback
        self.node.on_log = self._enqueue_log

        # Set up UI Components
        self._build_styles()
        self._build_header()
        self._build_tabs()
        self._build_status_bar()

        # Periodic background UI refresher
        self._refresh_timer()

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Treeview", font=("Segoe UI", 9), rowheight=24)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        style.configure("Header.TLabel", font=("Segoe UI", 10, "bold"))

    def _build_header(self):
        header_frame = ttk.LabelFrame(self.root, text="Node Status & Configuration", padding=10)
        header_frame.pack(fill=tk.X, padx=10, pady=5)

        info_text = (
            f"Node ID: {self.node.node_id}  |  "
            f"TCP Seeding Port: {self.node.tcp_port}  |  "
            f"UDP Discovery Port: {self.node.udp_port}"
        )
        ttk.Label(header_frame, text=info_text, style="Header.TLabel").pack(side=tk.LEFT, padx=5)

        self.lbl_peer_count = ttk.Label(header_frame, text="Active Peers: 0", foreground="blue")
        self.lbl_peer_count.pack(side=tk.RIGHT, padx=5)

    def _build_tabs(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.tab_network = ttk.Frame(self.notebook)
        self.tab_my_files = ttk.Frame(self.notebook)
        self.tab_peers = ttk.Frame(self.notebook)
        self.tab_logs = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_network, text=" Network Explorer & Downloads ")
        self.notebook.add(self.tab_my_files, text=" My Seeded Files ")
        self.notebook.add(self.tab_peers, text=" Connected Peers ")
        self.notebook.add(self.tab_logs, text=" Live Protocol Logs ")

        self._init_network_tab()
        self._init_my_files_tab()
        self._init_peers_tab()
        self._init_logs_tab()

    def _init_network_tab(self):
        # Controls Frame
        ctrl_frame = ttk.Frame(self.tab_network, padding=5)
        ctrl_frame.pack(fill=tk.X)

        ttk.Button(ctrl_frame, text="Refresh Network Files", command=self._action_refresh_network).pack(side=tk.LEFT, padx=5)
        ttk.Label(ctrl_frame, text="Search:").pack(side=tk.LEFT, padx=5)
        self.ent_search = ttk.Entry(ctrl_frame, width=25)
        self.ent_search.pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl_frame, text="Filter", command=self._action_filter_network).pack(side=tk.LEFT, padx=5)

        ttk.Button(ctrl_frame, text="Download Selected File", command=self._action_download_selected).pack(side=tk.RIGHT, padx=5)

        # Network Files Treeview
        tree_frame = ttk.Frame(self.tab_network)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        cols = ("name", "size", "chunks", "seeder", "file_id")
        self.tree_network = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        self.tree_network.heading("name", text="File Name")
        self.tree_network.heading("size", text="Size")
        self.tree_network.heading("chunks", text="Chunks")
        self.tree_network.heading("seeder", text="Seeder Node")
        self.tree_network.heading("file_id", text="File SHA-256 ID")

        self.tree_network.column("name", width=220)
        self.tree_network.column("size", width=100)
        self.tree_network.column("chunks", width=80)
        self.tree_network.column("seeder", width=140)
        self.tree_network.column("file_id", width=240)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree_network.yview)
        self.tree_network.configure(yscrollcommand=scrollbar.set)
        self.tree_network.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Download Progress Area
        prog_frame = ttk.LabelFrame(self.tab_network, text="Active Transfer Progress", padding=8)
        prog_frame.pack(fill=tk.X, padx=5, pady=5)

        self.progress_bar = ttk.Progressbar(prog_frame, orient=tk.HORIZONTAL, mode="determinate")
        self.progress_bar.pack(fill=tk.X, pady=3)

        self.lbl_transfer_status = ttk.Label(prog_frame, text="Idle - No active transfers")
        self.lbl_transfer_status.pack(side=tk.LEFT)

    def _init_my_files_tab(self):
        ctrl_frame = ttk.Frame(self.tab_my_files, padding=5)
        ctrl_frame.pack(fill=tk.X)

        ttk.Button(ctrl_frame, text="Share New File...", command=self._action_share_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl_frame, text="Open Storage Folder", command=self._action_open_storage_folder).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl_frame, text="Open Downloads Folder", command=self._action_open_downloads_folder).pack(side=tk.LEFT, padx=5)

        tree_frame = ttk.Frame(self.tab_my_files)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        cols = ("name", "size", "chunks", "file_id")
        self.tree_my_files = ttk.Treeview(tree_frame, columns=cols, show="headings")
        self.tree_my_files.heading("name", text="File Name")
        self.tree_my_files.heading("size", text="File Size")
        self.tree_my_files.heading("chunks", text="Total Chunks")
        self.tree_my_files.heading("file_id", text="SHA-256 Digest")

        self.tree_my_files.column("name", width=240)
        self.tree_my_files.column("size", width=120)
        self.tree_my_files.column("chunks", width=100)
        self.tree_my_files.column("file_id", width=300)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree_my_files.yview)
        self.tree_my_files.configure(yscrollcommand=scrollbar.set)
        self.tree_my_files.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _init_peers_tab(self):
        ctrl_frame = ttk.Frame(self.tab_peers, padding=5)
        ctrl_frame.pack(fill=tk.X)

        ttk.Label(ctrl_frame, text="Manual Add IP:").pack(side=tk.LEFT, padx=5)
        self.ent_peer_ip = ttk.Entry(ctrl_frame, width=15)
        self.ent_peer_ip.insert(0, "127.0.0.1")
        self.ent_peer_ip.pack(side=tk.LEFT, padx=2)

        ttk.Label(ctrl_frame, text="Port:").pack(side=tk.LEFT, padx=5)
        self.ent_peer_port = ttk.Entry(ctrl_frame, width=8)
        self.ent_peer_port.pack(side=tk.LEFT, padx=2)

        ttk.Button(ctrl_frame, text="Add Peer", command=self._action_add_manual_peer).pack(side=tk.LEFT, padx=5)

        tree_frame = ttk.Frame(self.tab_peers)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        cols = ("node_id", "address", "shared", "last_seen")
        self.tree_peers = ttk.Treeview(tree_frame, columns=cols, show="headings")
        self.tree_peers.heading("node_id", text="Peer Node ID")
        self.tree_peers.heading("address", text="IP Address : TCP Port")
        self.tree_peers.heading("shared", text="Shared Files")
        self.tree_peers.heading("last_seen", text="Last Seen (Heartbeat)")

        self.tree_peers.column("node_id", width=220)
        self.tree_peers.column("address", width=180)
        self.tree_peers.column("shared", width=100)
        self.tree_peers.column("last_seen", width=160)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree_peers.yview)
        self.tree_peers.configure(yscrollcommand=scrollbar.set)
        self.tree_peers.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _init_logs_tab(self):
        log_frame = ttk.Frame(self.tab_logs, padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.txt_logs = tk.Text(log_frame, wrap=tk.WORD, font=("Consolas", 9), bg="#1e1e1e", fg="#00ff66")
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.txt_logs.yview)
        self.txt_logs.configure(yscrollcommand=scrollbar.set)
        self.txt_logs.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_status_bar(self):
        self.lbl_status = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.lbl_status.pack(side=tk.BOTTOM, fill=tk.X)

    # --- Actions & Handlers ---

    def _enqueue_log(self, msg: str):
        def _append():
            if self.txt_logs:
                self.txt_logs.insert(tk.END, msg + "\n")
                self.txt_logs.see(tk.END)
        self.root.after(0, _append)

    def _refresh_timer(self):
        self._update_peers_ui()
        self._update_my_files_ui()
        self.root.after(3000, self._refresh_timer)

    def _update_peers_ui(self):
        peers = self.node.discovery.get_active_peers() if self.node.discovery else []
        self.lbl_peer_count.config(text=f"Active Peers: {len(peers)}")

        for item in self.tree_peers.get_children():
            self.tree_peers.delete(item)

        now = time.time()
        for p in peers:
            ago = max(0, int(now - p.last_seen))
            self.tree_peers.insert(
                "",
                tk.END,
                values=(p.node_id, f"{p.ip}:{p.tcp_port}", p.shared_count, f"{ago}s ago"),
            )

    def _update_my_files_ui(self):
        for item in self.tree_my_files.get_children():
            self.tree_my_files.delete(item)

        for f in self.node.file_manager.list_shared_files():
            size_kb = f["file_size"] / 1024.0
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.2f} MB"
            self.tree_my_files.insert(
                "",
                tk.END,
                values=(f["file_name"], size_str, f["chunk_count"], f["file_id"]),
            )

    def _action_share_file(self):
        filepath = filedialog.askopenfilename(title="Select File to Share")
        if filepath:
            try:
                manifest = self.node.file_manager.add_file(filepath)
                self._update_my_files_ui()
                messagebox.showinfo(
                    "File Shared",
                    f"File '{manifest.file_name}' ({manifest.file_size} B) successfully indexed into {manifest.chunk_count} chunks.",
                )
            except Exception as e:
                messagebox.showerror("Error", f"Failed to share file: {e}")

    def _action_open_storage_folder(self):
        os.startfile(self.node.file_manager.storage_dir)

    def _action_open_downloads_folder(self):
        os.startfile(self.node.file_manager.download_dir)

    def _action_add_manual_peer(self):
        ip = self.ent_peer_ip.get().strip()
        port_str = self.ent_peer_port.get().strip()
        if not ip or not port_str:
            messagebox.showwarning("Input Error", "Please provide both IP and Port.")
            return
        try:
            port = int(port_str)
            if self.node.discovery:
                self.node.discovery.add_peer_manually(ip, port)
                self._update_peers_ui()
                messagebox.showinfo("Success", f"Added peer {ip}:{port}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add peer: {e}")

    def _action_refresh_network(self):
        def _fetch():
            peers = self.node.discovery.get_active_peers() if self.node.discovery else []
            collected = []
            for p in peers:
                try:
                    pfiles = self.node.query_peer_files(p.ip, p.tcp_port)
                    for f in pfiles:
                        collected.append((f, p))
                except Exception:
                    pass

            def _update():
                for item in self.tree_network.get_children():
                    self.tree_network.delete(item)
                for f, p in collected:
                    size_kb = f["file_size"] / 1024.0
                    size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.2f} MB"
                    self.tree_network.insert(
                        "",
                        tk.END,
                        values=(f["file_name"], size_str, f["chunk_count"], f"{p.ip}:{p.tcp_port}", f["file_id"]),
                    )
            self.root.after(0, _update)

        threading.Thread(target=_fetch, daemon=True).start()

    def _action_filter_network(self):
        query = self.ent_search.get().strip().lower()
        if not query:
            self._action_refresh_network()
            return
        for child in self.tree_network.get_children():
            values = self.tree_network.item(child, "values")
            if query not in values[0].lower():
                self.tree_network.delete(child)

    def _action_download_selected(self):
        selected = self.tree_network.selection()
        if not selected:
            messagebox.showwarning("Select File", "Please select a file from the list to download.")
            return

        values = self.tree_network.item(selected[0], "values")
        file_name = values[0]
        file_id = values[4]

        self.progress_bar["value"] = 0
        self.lbl_transfer_status.config(text=f"Connecting to swarm for '{file_name}'...")

        def _bg_download():
            try:
                def _prog(done, total, speed):
                    def _update_ui():
                        pct = (done / total) * 100.0 if total > 0 else 100.0
                        self.progress_bar["value"] = pct
                        self.lbl_transfer_status.config(
                            text=f"Downloading '{file_name}': {done}/{total} chunks ({pct:.1f}%) | {speed:.2f} KB/s"
                        )
                    self.root.after(0, _update_ui)

                dest_path = self.node.download_file(file_id=file_id, progress_cb=_prog)

                def _done_ui():
                    self.lbl_transfer_status.config(text=f"Download Completed & Verified! Saved to: {dest_path}")
                    messagebox.showinfo("Download Complete", f"Successfully downloaded and verified SHA-256 for:\n{dest_path}")
                    self._update_my_files_ui()
                self.root.after(0, _done_ui)

            except Exception as e:
                def _err_ui():
                    self.lbl_transfer_status.config(text=f"Download failed: {e}")
                    messagebox.showerror("Download Error", f"Swarm download failed:\n{e}")
                self.root.after(0, _err_ui)

        threading.Thread(target=_bg_download, daemon=True).start()

    def _on_close(self):
        self.node.stop()
        self.root.destroy()

    def start(self):
        self.root.mainloop()

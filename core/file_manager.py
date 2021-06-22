# Manages shared files and tracks chunks

import os
import threading
from typing import Dict, List, Optional, Any
from .chunker import FileManifest, FileBitfield, create_manifest, read_chunk_from_file
from protocol.constants import DEFAULT_CHUNK_SIZE

class FileManager:
    def __init__(self, storage_dir: str, download_dir: str, chunk_size: int = DEFAULT_CHUNK_SIZE):
        self.storage_dir = os.path.abspath(storage_dir)
        self.download_dir = os.path.abspath(download_dir)
        self.chunk_size = chunk_size
        os.makedirs(self.storage_dir, exist_ok=True)
        os.makedirs(self.download_dir, exist_ok=True)
        self.files = {}
        self.lock = threading.Lock()

    def add_file(self, filepath: str) -> FileManifest:
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        manifest = create_manifest(filepath, self.chunk_size)
        bitfield = FileBitfield(manifest.chunk_count, initial_value=True)
        with self.lock:
            self.files[manifest.file_id] = (filepath, manifest, bitfield)
        return manifest

    def refresh_storage(self) -> List[FileManifest]:
        added = []
        with self.lock:
            for fname in os.listdir(self.storage_dir):
                fpath = os.path.join(self.storage_dir, fname)
                if os.path.isfile(fpath):
                    try:
                        manifest = create_manifest(fpath, self.chunk_size)
                        bitfield = FileBitfield(manifest.chunk_count, initial_value=True)
                        self.files[manifest.file_id] = (fpath, manifest, bitfield)
                        added.append(manifest)
                    except Exception:
                        pass
        return added

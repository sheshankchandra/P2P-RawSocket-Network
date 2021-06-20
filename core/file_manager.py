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

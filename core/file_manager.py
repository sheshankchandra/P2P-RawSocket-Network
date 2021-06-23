# Manages shared files, tracks which chunks we have,
# and reads chunk data from disk when peers request it.

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

        # Mapping: file_id -> (filepath, FileManifest, FileBitfield)
        self.files: Dict[str, tuple[str, FileManifest, FileBitfield]] = {}
        self.lock = threading.Lock()

        self.refresh_storage()

    def add_file(self, filepath: str) -> FileManifest:
        # Indexes a file to share with other peers
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        manifest = create_manifest(filepath, self.chunk_size)
        bitfield = FileBitfield(manifest.chunk_count, initial_value=True)
        with self.lock:
            self.files[manifest.file_id] = (filepath, manifest, bitfield)
        return manifest

    def refresh_storage(self) -> List[FileManifest]:
        # Scans the storage folder and loads any existing files
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

    def list_shared_files(self) -> List[Dict[str, Any]]:
        with self.lock:
            result = []
            for file_id, (fpath, manifest, bitfield) in self.files.items():
                result.append({
                    "file_id": file_id,
                    "file_name": manifest.file_name,
                    "file_size": manifest.file_size,
                    "chunk_count": manifest.chunk_count,
                    "chunk_size": manifest.chunk_size,
                    "completed_chunks": bitfield.count_completed(),
                    "is_complete": bitfield.is_complete(),
                })
            return result

    def get_manifest(self, file_id: str) -> Optional[FileManifest]:
        with self.lock:
            entry = self.files.get(file_id)
            if entry:
                return entry[1]
            return None

    def get_bitfield(self, file_id: str) -> Optional[FileBitfield]:
        with self.lock:
            entry = self.files.get(file_id)
            if entry:
                return entry[2]
            return None

    def get_chunk(self, file_id: str, chunk_index: int) -> Optional[bytes]:
        with self.lock:
            entry = self.files.get(file_id)
            if not entry:
                return None
            filepath, manifest, bitfield = entry

        if chunk_index < 0 or chunk_index >= manifest.chunk_count:
            return None

        if not bitfield.has_piece(chunk_index):
            return None

        return read_chunk_from_file(filepath, chunk_index, self.chunk_size)

    def mark_download_complete(self, file_id: str, downloaded_path: str, manifest: FileManifest):
        # Once a download finishes, start seeding it
        bitfield = FileBitfield(manifest.chunk_count, initial_value=True)
        with self.lock:
            self.files[file_id] = (downloaded_path, manifest, bitfield)

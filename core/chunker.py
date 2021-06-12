# File chunking and SHA-256 digests

import hashlib
from typing import Dict, Any, List

def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

class FileManifest:
    def __init__(self, file_id: str, file_name: str, file_size: int, chunk_size: int, chunk_count: int, chunk_hashes: List[str]):
        self.file_id = file_id
        self.file_name = file_name
        self.file_size = file_size
        self.chunk_size = chunk_size
        self.chunk_count = chunk_count
        self.chunk_hashes = chunk_hashes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_id": self.file_id,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "chunk_size": self.chunk_size,
            "chunk_count": self.chunk_count,
            "chunk_hashes": self.chunk_hashes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)

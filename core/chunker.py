try:
    from bitarray import bitarray
    USE_BITARRAY = True
except ImportError:
    USE_BITARRAY = False

class FileBitfield:
    def __init__(self, num_chunks: int, initial_value: bool = False):
        self.num_chunks = num_chunks
        if USE_BITARRAY:
            self.bits = bitarray(num_chunks)
            self.bits.setall(1 if initial_value else 0)
        else:
            self.bits = [1 if initial_value else 0] * num_chunks

    def set_piece(self, index: int, value: bool = True):
        self.bits[index] = 1 if value else 0

    def has_piece(self, index: int) -> bool:
        return bool(self.bits[index])

    def is_complete(self) -> bool:
        return self.bits.all() if USE_BITARRAY else all(self.bits)

    def count_completed(self) -> int:
        return self.bits.count(1) if USE_BITARRAY else sum(self.bits)

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

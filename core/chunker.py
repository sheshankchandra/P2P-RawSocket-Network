# Splits files into chunks, calculates SHA-256 hashes,
# and tracks which chunks we have using bitarray.

import os
import math
import hashlib
from typing import Dict, Any, List, Optional
from protocol.constants import DEFAULT_CHUNK_SIZE

try:
    from bitarray import bitarray
    USE_BITARRAY = True
except ImportError:
    USE_BITARRAY = False


class FileBitfield:
    # Keeps track of which chunks of a file we currently possess.
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
        if USE_BITARRAY:
            return self.bits.all()
        return all(self.bits)

    def count_completed(self) -> int:
        if USE_BITARRAY:
            return self.bits.count(1)
        return sum(self.bits)

    def to_bytes(self) -> bytes:
        if USE_BITARRAY:
            return self.bits.tobytes()
        b = bytearray((self.num_chunks + 7) // 8)
        for i in range(self.num_chunks):
            if self.bits[i]:
                b[i // 8] |= (1 << (7 - (i % 8)))
        return bytes(b)

    @classmethod
    def from_bytes(cls, data: bytes, num_chunks: int) -> "FileBitfield":
        bf = cls(num_chunks, initial_value=False)
        if USE_BITARRAY:
            ba = bitarray()
            ba.frombytes(data)
            bf.bits = ba[:num_chunks]
        else:
            for i in range(num_chunks):
                if data[i // 8] & (1 << (7 - (i % 8))):
                    bf.bits[i] = 1
        return bf

    def __repr__(self) -> str:
        completed = self.count_completed()
        return f"<Bitfield {completed}/{self.num_chunks} chunks>"


class FileManifest:
    # Stores metadata for a shared file and hashes for every chunk
    def __init__(
        self,
        file_id: str,
        file_name: str,
        file_size: int,
        chunk_size: int,
        chunk_count: int,
        chunk_hashes: List[str],
    ):
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
    def from_dict(cls, data: Dict[str, Any]) -> "FileManifest":
        return cls(
            file_id=data["file_id"],
            file_name=data["file_name"],
            file_size=data["file_size"],
            chunk_size=data["chunk_size"],
            chunk_count=data["chunk_count"],
            chunk_hashes=data["chunk_hashes"],
        )


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def create_manifest(filepath: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> FileManifest:
    # Reads the file, splits it into pieces, and calculates SHA-256 for each piece
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    file_size = os.path.getsize(filepath)
    file_name = os.path.basename(filepath)
    chunk_count = max(1, math.ceil(file_size / chunk_size)) if file_size > 0 else 1

    chunk_hashes = []
    file_hasher = hashlib.sha256()

    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                if file_size == 0 and len(chunk_hashes) == 0:
                    chunk_hashes.append(hashlib.sha256(b"").hexdigest())
                break
            chunk_hashes.append(compute_sha256(chunk))
            file_hasher.update(chunk)

    file_id = file_hasher.hexdigest()

    return FileManifest(
        file_id=file_id,
        file_name=file_name,
        file_size=file_size,
        chunk_size=chunk_size,
        chunk_count=chunk_count,
        chunk_hashes=chunk_hashes,
    )


def read_chunk_from_file(filepath: str, chunk_index: int, chunk_size: int = DEFAULT_CHUNK_SIZE) -> bytes:
    # Seeks directly to the chunk offset instead of reading the whole file into RAM
    with open(filepath, "rb") as f:
        f.seek(chunk_index * chunk_size)
        return f.read(chunk_size)


def verify_chunk(chunk_data: bytes, expected_hash: str) -> bool:
    return compute_sha256(chunk_data) == expected_hash


def reassemble_file(
    output_filepath: str,
    chunks: Dict[int, bytes],
    manifest: FileManifest,
) -> bool:
    # Writes all chunks sequentially into the output file and checks the final file hash
    os.makedirs(os.path.dirname(os.path.abspath(output_filepath)), exist_ok=True)

    with open(output_filepath, "wb") as f:
        for idx in range(manifest.chunk_count):
            if idx not in chunks:
                raise ValueError(f"Missing chunk {idx} during reassembly")
            f.write(chunks[idx])

    # Re-verify full file hash
    computed_file_id = create_manifest(output_filepath, manifest.chunk_size).file_id
    if computed_file_id != manifest.file_id:
        raise ValueError(
            f"File integrity check failed: expected {manifest.file_id}, got {computed_file_id}"
        )

    return True

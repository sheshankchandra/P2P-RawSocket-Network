# Helper functions to encode and decode payloads for different message types.
# JSON is used for metadata, and binary struct packing is used for chunk data.

import json
import struct
from typing import Dict, Any, List, Tuple


def encode_json_payload(data: Any) -> bytes:
    return json.dumps(data).encode("utf-8")


def decode_json_payload(payload: bytes) -> Any:
    return json.loads(payload.decode("utf-8"))


# Handshake payload
def encode_handshake(node_id: str, tcp_port: int, client_name: str = "P2P-Node") -> bytes:
    return encode_json_payload({
        "node_id": node_id,
        "tcp_port": tcp_port,
        "client": client_name,
    })


def decode_handshake(payload: bytes) -> Dict[str, Any]:
    return decode_json_payload(payload)


# Shared files list
def encode_file_list(files: List[Dict[str, Any]]) -> bytes:
    return encode_json_payload({"files": files})


def decode_file_list(payload: bytes) -> List[Dict[str, Any]]:
    data = decode_json_payload(payload)
    return data.get("files", [])


# File metadata (manifest)
def encode_file_meta_req(file_id: str) -> bytes:
    return encode_json_payload({"file_id": file_id})


def decode_file_meta_req(payload: bytes) -> str:
    data = decode_json_payload(payload)
    return data["file_id"]


def encode_file_meta_resp(manifest: Dict[str, Any]) -> bytes:
    return encode_json_payload(manifest)


def decode_file_meta_resp(payload: bytes) -> Dict[str, Any]:
    return decode_json_payload(payload)


# Chunk requests and responses
# Chunk request: 64-char sha256 hex + 4-byte chunk index
CHUNK_REQ_FORMAT = "!64sI"
CHUNK_REQ_SIZE = struct.calcsize(CHUNK_REQ_FORMAT)

# Chunk response: 64-char sha256 hex + 4-byte index + 4-byte length + raw chunk bytes
CHUNK_RESP_HEADER_FORMAT = "!64sII"
CHUNK_RESP_HEADER_SIZE = struct.calcsize(CHUNK_RESP_HEADER_FORMAT)


def encode_chunk_req(file_id: str, chunk_index: int) -> bytes:
    return struct.pack(CHUNK_REQ_FORMAT, file_id.encode("ascii"), chunk_index)


def decode_chunk_req(payload: bytes) -> Tuple[str, int]:
    file_id_raw, chunk_index = struct.unpack(CHUNK_REQ_FORMAT, payload)
    return file_id_raw.decode("ascii"), chunk_index


def encode_chunk_resp(file_id: str, chunk_index: int, chunk_data: bytes) -> bytes:
    header = struct.pack(
        CHUNK_RESP_HEADER_FORMAT,
        file_id.encode("ascii"),
        chunk_index,
        len(chunk_data),
    )
    return header + chunk_data


def decode_chunk_resp(payload: bytes) -> Tuple[str, int, bytes]:
    if len(payload) < CHUNK_RESP_HEADER_SIZE:
        raise ValueError("Payload too small for chunk response header")
    file_id_raw, chunk_index, data_len = struct.unpack(
        CHUNK_RESP_HEADER_FORMAT, payload[:CHUNK_RESP_HEADER_SIZE]
    )
    chunk_data = payload[CHUNK_RESP_HEADER_SIZE : CHUNK_RESP_HEADER_SIZE + data_len]
    return file_id_raw.decode("ascii"), chunk_index, chunk_data

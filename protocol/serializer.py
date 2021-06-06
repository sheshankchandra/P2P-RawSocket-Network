# Payload encoders and decoders

import json
from typing import Any

def encode_json_payload(data: Any) -> bytes:
    return json.dumps(data).encode("utf-8")

def decode_json_payload(payload: bytes) -> Any:
    return json.loads(payload.decode("utf-8"))

def encode_handshake(node_id: str, tcp_port: int, client_name: str = "P2P-Node") -> bytes:
    return encode_json_payload({"node_id": node_id, "tcp_port": tcp_port, "client": client_name})

def decode_handshake(payload: bytes):
    return decode_json_payload(payload)

def encode_file_list(files):
    return encode_json_payload({"files": files})

def decode_file_list(payload: bytes):
    return decode_json_payload(payload).get("files", [])

def encode_file_meta_req(file_id: str) -> bytes:
    return encode_json_payload({"file_id": file_id})

def decode_file_meta_req(payload: bytes) -> str:
    return decode_json_payload(payload)["file_id"]

def encode_file_meta_resp(manifest):
    return encode_json_payload(manifest)

def decode_file_meta_resp(payload: bytes):
    return decode_json_payload(payload)

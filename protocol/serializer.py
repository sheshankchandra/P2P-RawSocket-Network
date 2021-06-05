# Payload encoders and decoders

import json
from typing import Any

def encode_json_payload(data: Any) -> bytes:
    return json.dumps(data).encode("utf-8")

def decode_json_payload(payload: bytes) -> Any:
    return json.loads(payload.decode("utf-8"))

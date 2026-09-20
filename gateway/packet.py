#!/usr/bin/env python3
"""BitChat Wire Protocol Packet Builder.

Constructs binary packets compatible with bitchat-android's BinaryProtocol.kt.
Packets use a 13-byte header followed by optional fields, payload, and signature.

Wire format:
    [Type:1B][TTL:1B][Flags:1B][SenderID:8B][PayloadLen:2B(BE)]
    [RecipientID:8B?][MessageID:16B][Timestamp:8B(BE)]
    [Payload:variable][Signature:64B?]

Critical: Ed25519 signature signs (type + sender_id + timestamp + payload)
          but EXCLUDES TTL — this allows mesh relay nodes to decrement
          hop count without breaking the signature.
"""

import hashlib
import struct
import time
import uuid
import logging

try:
    import lz4.frame
    HAS_LZ4 = True
except ImportError:
    HAS_LZ4 = False
    logging.warning("lz4 library not installed. Compression will be skipped.")

# Constants
PACKET_TYPE_ANNOUNCE = 0x01
PACKET_TYPE_KEY_EXCHANGE = 0x02
PACKET_TYPE_MESSAGE = 0x03
PACKET_TYPE_FILE_TRANSFER = 0x04
PACKET_TYPE_LEAVE = 0x05
PACKET_TYPE_PING = 0x06

FLAG_HAS_RECIPIENT = 0x01
FLAG_HAS_SIGNATURE = 0x02
FLAG_COMPRESSED = 0x04
FLAG_SOURCE_ROUTED = 0x08

DEFAULT_TTL = 7

BLE_SERVICE_UUID = "f47b5e2d-4a9e-4c5a-9b3f-8e1d2c3a4b5c"
BLE_CHAR_UUID = "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d"

def compute_sender_id(public_key_bytes: bytes) -> bytes:
    """Compute 8-byte sender ID matching BitChat derivation."""
    return hashlib.sha256(public_key_bytes).digest()[:8]

def build_broadcast_packet(payload_text: str, private_key, public_key_bytes: bytes, ttl: int = DEFAULT_TTL) -> bytes:
    """Build a signed broadcast mesh packet."""
    payload_bytes = payload_text.encode('utf-8')
    flags = FLAG_HAS_SIGNATURE

    if HAS_LZ4 and len(payload_bytes) > 100:
        # Note: lz4 frame format might add headers, ensure bitchat protocol compatibility
        # Bitchat android uses LZ4 block or frame depending on implementation.
        # Assuming simple compress:
        try:
            import lz4.block
            payload_bytes = lz4.block.compress(payload_bytes, store_size=False)
            flags |= FLAG_COMPRESSED
        except ImportError:
            pass

    sender_id = compute_sender_id(public_key_bytes)
    payload_len = len(payload_bytes)

    # Message ID (16 bytes)
    msg_id = uuid.uuid4().bytes

    # Timestamp (8 bytes BE)
    timestamp_ms = int(time.time() * 1000)
    timestamp_bytes = struct.pack(">Q", timestamp_ms)

    # Signature computation
    # Sign over: type_byte + sender_id + timestamp_bytes + payload_bytes
    sign_data = struct.pack(">B", PACKET_TYPE_MESSAGE) + sender_id + timestamp_bytes + payload_bytes
    signature = private_key.sign(sign_data)

    # Header structure: Type(1) + TTL(1) + Flags(1) + SenderID(8) + PayloadLen(2)
    header = struct.pack(">BBB8sH", PACKET_TYPE_MESSAGE, ttl, flags, sender_id, payload_len)

    packet = header + msg_id + timestamp_bytes + payload_bytes + signature
    return packet

def parse_packet_header(data: bytes) -> dict:
    """Parse the 13-byte header for debugging."""
    if len(data) < 13:
        raise ValueError("Data too short for header")
    type_byte, ttl, flags, sender_id, payload_len = struct.unpack(">BBB8sH", data[:13])
    return {
        "type": type_byte,
        "ttl": ttl,
        "flags": flags,
        "sender_id": sender_id,
        "payload_len": payload_len
    }

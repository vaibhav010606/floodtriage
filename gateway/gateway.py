#!/usr/bin/env python3
"""Flood Alert Gateway — CAP Alert to Bluetooth Mesh Broadcast.

This script uses bitchat-cli's real protocol implementation to send
flood alerts over the Bluetooth mesh. It handles the full lifecycle:
  1. Scan for bitchat peers
  2. Connect and send ANNOUNCE (so peers accept our messages)
  3. Send the signed MESSAGE packet
  4. Wait briefly for relay, then disconnect

Usage:
    python gateway.py --text "FLOOD ALERT: Majuli — river rising. Move to higher ground."
    python gateway.py --cap-file alert.xml
    python gateway.py --dry-run --text "Test alert"
"""

import argparse
import asyncio
import hashlib
import os
import sys
import time

import yaml

# Use bitchat-cli's real protocol (installed via pip install bitchat-cli)
from bitchat_cli.protocol import (
    AnnouncementPacket,
    BitchatPacket,
    MessageType,
    DEFAULT_TTL,
)
from bitchat_cli.identity import IdentityKeys

try:
    from bleak import BleakClient, BleakScanner
    HAS_BLEAK = True
except ImportError:
    HAS_BLEAK = False

# Real bitchat UUIDs
SERVICE_UUID = "f47b5e2d-4a9e-4c5a-9b3f-8e1d2c3a4b5c"
CHARACTERISTIC_UUID = "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d"

CONNECTION_TIMEOUT = 15.0
MAX_FRAME_SIZE = 480


def load_config(config_path="config.yaml"):
    if not os.path.exists(config_path):
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


async def broadcast_alert(alert_text: str, nickname: str = "FloodGateway"):
    """Connect to nearby bitchat peers and send an alert message."""
    if not HAS_BLEAK:
        print("Error: bleak library not installed. Run: pip install bleak")
        return False

    # Create a fresh identity for this gateway session
    identity = IdentityKeys()
    peer_id = os.urandom(8)  # random 8-byte peer ID

    print(f"\n[*] Scanning for BitChat devices for 5 seconds...")
    devices_dict = await BleakScanner.discover(timeout=5.0, return_adv=True)

    # Find devices advertising the BitChat service
    bitchat_devices = []
    for addr, (device, adv) in devices_dict.items():
        name = device.name or "Unknown"
        uuids = [u.lower() for u in adv.service_uuids]
        is_bitchat = SERVICE_UUID in uuids
        marker = " <-- BitChat!" if is_bitchat else ""
        print(f"  - {name} ({device.address}){marker}")
        if is_bitchat:
            bitchat_devices.append(device)

    if not bitchat_devices:
        print("\n[!] No BitChat devices found nearby.")
        return False

    print(f"\nFound {len(bitchat_devices)} BitChat device(s). Connecting...")

    # Build the ANNOUNCE packet (so the peer lists us and accepts our messages)
    announce_payload = AnnouncementPacket(
        nickname=nickname,
        noise_public_key=identity.noise_public_key_bytes(),
        signing_public_key=identity.signing_public_key_bytes(),
    ).encode()

    announce_packet = BitchatPacket(
        type=MessageType.ANNOUNCE,
        sender_id=peer_id,
        recipient_id=None,
        payload=announce_payload,
        ttl=DEFAULT_TTL,
    )
    announce_packet.signature = identity.sign(announce_packet.data_for_signing())
    announce_bytes = announce_packet.encode()

    # Build the MESSAGE packet
    message_packet = BitchatPacket(
        type=MessageType.MESSAGE,
        sender_id=peer_id,
        recipient_id=None,
        payload=alert_text.encode("utf-8"),
        ttl=DEFAULT_TTL,
    )
    message_packet.signature = identity.sign(message_packet.data_for_signing())
    message_bytes = message_packet.encode()

    print(f"  Announce packet: {len(announce_bytes)} bytes")
    print(f"  Message packet:  {len(message_bytes)} bytes")

    success_count = 0
    for device in bitchat_devices:
        for attempt in range(1, 4):
            try:
                print(f"\n  [{device.address}] Attempt {attempt}/3 -- connecting...")
                async with BleakClient(device, timeout=CONNECTION_TIMEOUT) as client:
                    print(f"  [{device.address}] Connected! MTU: {client.mtu_size}")

                    # Step 1: Subscribe to notifications (required by the protocol)
                    received_packets = []
                    def on_notify(_char, data):
                        received_packets.append(bytes(data))
                    
                    await client.start_notify(CHARACTERISTIC_UUID, on_notify)
                    print(f"  [{device.address}] Subscribed to notifications.")

                    # Step 2: Send ANNOUNCE so the peer knows who we are
                    await client.write_gatt_char(CHARACTERISTIC_UUID, announce_bytes, response=False)
                    print(f"  [{device.address}] Sent ANNOUNCE as '{nickname}'")
                    await asyncio.sleep(0.5)  # Let the peer process the announce

                    # Step 3: Send the actual alert MESSAGE
                    await client.write_gatt_char(CHARACTERISTIC_UUID, message_bytes, response=False)
                    print(f"  [OK] ALERT SENT to {device.address}!")
                    success_count += 1

                    # Wait a moment for relay acknowledgment
                    await asyncio.sleep(1.0)
                    
                    await client.stop_notify(CHARACTERISTIC_UUID)
                    break  # Success, don't retry

            except Exception as e:
                print(f"  [{device.address}] Attempt {attempt} failed: {type(e).__name__}: {e}")
                if attempt < 3:
                    print(f"  Retrying in 2 seconds...")
                    await asyncio.sleep(2)

    if success_count > 0:
        print(f"\n[SUCCESS] Broadcasted alert to {success_count} device(s)!")
        print(f"   The alert will relay up to 7 hops across the mesh network.")
    else:
        print("\n[!] Failed to send alert to any device.")

    return success_count > 0


def main():
    parser = argparse.ArgumentParser(description="Flood Alert Gateway")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--cap-file", help="Path to CAP alert XML file")
    parser.add_argument("--text", help="Direct text to broadcast")
    parser.add_argument("--nickname", default="FloodGateway", help="Gateway nickname on mesh")
    parser.add_argument("--dry-run", action="store_true", help="Build packets but don't send")

    args = parser.parse_args()

    # Determine the alert text
    payload_text = ""

    if args.text:
        payload_text = args.text
    elif args.cap_file:
        import xml.etree.ElementTree as ET
        try:
            tree = ET.parse(args.cap_file)
            root = tree.getroot()
            ns = {'cap': 'urn:oasis:names:tc:emergency:cap:1.2'}
            info = root.find("cap:info", ns)
            if info is not None:
                headline = info.findtext("cap:headline", default="", namespaces=ns)
                instruction = info.findtext("cap:instruction", default="", namespaces=ns)
                payload_text = f"{headline}\n{instruction}"
            else:
                payload_text = "CAP Alert: Missing info block"
        except Exception as e:
            print(f"Error parsing CAP file: {e}")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

    print(f"\n--- Payload ---\n{payload_text}\n")
    print(f"Payload size: {len(payload_text.encode('utf-8'))} bytes")

    if args.dry_run:
        # Build packets to verify they're valid, but don't send
        identity = IdentityKeys()
        peer_id = os.urandom(8)
        
        msg_packet = BitchatPacket(
            type=MessageType.MESSAGE,
            sender_id=peer_id,
            recipient_id=None,
            payload=payload_text.encode("utf-8"),
            ttl=DEFAULT_TTL,
        )
        msg_packet.signature = identity.sign(msg_packet.data_for_signing())
        encoded = msg_packet.encode()
        
        print(f"Packet built: {len(encoded)} bytes (with PKCS#7 padding)")
        print(f"Packet hex (first 64 bytes): {encoded[:64].hex()}")
        print(f"\n[DRY RUN] Packet valid. No BLE broadcast performed.")
        sys.exit(0)

    # Actually broadcast
    asyncio.run(broadcast_alert(payload_text, nickname=args.nickname))


if __name__ == "__main__":
    main()

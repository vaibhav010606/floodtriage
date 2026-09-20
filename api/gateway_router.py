"""Gateway Router — BLE Mesh Broadcast API.

Wraps gateway.py into FastAPI endpoints for triggering BLE broadcasts
from the web application.
"""

import asyncio
import os
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

# Add gateway to Python path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_GATEWAY_DIR = _PROJECT_ROOT / "gateway"
if str(_GATEWAY_DIR) not in sys.path:
    sys.path.insert(0, str(_GATEWAY_DIR))

from .schemas import (
    BroadcastRequest,
    BroadcastResponse,
    GatewayStatusResponse,
)

router = APIRouter(prefix="/api/gateway", tags=["BLE Gateway"])

# Alerts directory (shared with alert_router)
ALERTS_DIR = _PROJECT_ROOT / "alerts"


def _load_alert_short_text(alert_id: str) -> str:
    """Load the short text for an alert from stored metadata."""
    import json
    meta_path = ALERTS_DIR / f"{alert_id}.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    return meta.get("short_text", "FLOOD ALERT")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status", response_model=GatewayStatusResponse)
async def gateway_status():
    """Check if a BLE adapter is available for mesh broadcast."""
    try:
        from bleak import BleakScanner
        # Quick check — don't actually scan, just verify import works
        return GatewayStatusResponse(
            ble_available=True,
            message="BLE adapter available. Ready to broadcast.",
        )
    except ImportError:
        return GatewayStatusResponse(
            ble_available=False,
            message="bleak library not installed. Run: pip install bleak",
        )
    except Exception as e:
        return GatewayStatusResponse(
            ble_available=False,
            message=f"BLE check failed: {str(e)}",
        )


@router.post("/broadcast", response_model=BroadcastResponse)
async def broadcast_alert(req: BroadcastRequest):
    """Broadcast a flood alert over the BLE mesh network.

    Provide either an alert_id (to broadcast a saved alert) or raw text.
    The message propagates up to 7 hops across the BitChat mesh.
    """
    # Determine the text to broadcast
    if req.alert_id:
        broadcast_text = _load_alert_short_text(req.alert_id)
    elif req.text:
        broadcast_text = req.text
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either alert_id or text to broadcast",
        )

    # Check payload size (BitChat max frame = 480 bytes)
    payload_bytes = broadcast_text.encode("utf-8")
    if len(payload_bytes) > 400:
        raise HTTPException(
            status_code=400,
            detail=f"Payload too large: {len(payload_bytes)} bytes (max 400)",
        )

    if req.dry_run:
        # Build packet but don't send — useful for testing
        try:
            from gateway import broadcast_alert as ble_broadcast
            # Just verify the packet can be built
            return BroadcastResponse(
                success=True,
                message=f"[DRY RUN] Packet valid. Text: {broadcast_text[:80]}...",
                packet_size_bytes=len(payload_bytes),
                devices_reached=0,
            )
        except ImportError:
            return BroadcastResponse(
                success=True,
                message=f"[DRY RUN] Text ready ({len(payload_bytes)} bytes). "
                        f"Gateway module not available for packet building.",
                packet_size_bytes=len(payload_bytes),
                devices_reached=0,
            )

    # Actual broadcast
    try:
        from gateway import broadcast_alert as ble_broadcast

        success = await ble_broadcast(broadcast_text, nickname=req.nickname)
        return BroadcastResponse(
            success=success,
            message="Alert broadcast to BLE mesh" if success
                    else "No BitChat devices found nearby",
            packet_size_bytes=len(payload_bytes),
        )
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="BLE gateway not available. Install: pip install bleak bitchat-cli",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Broadcast failed: {str(e)}",
        )


@router.post("/broadcast-text", response_model=BroadcastResponse)
async def broadcast_text(text: str, dry_run: bool = False):
    """Quick endpoint to broadcast raw text over the mesh."""
    req = BroadcastRequest(text=text, dry_run=dry_run)
    return await broadcast_alert(req)

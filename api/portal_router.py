"""Portal Router — Wi-Fi Captive Portal Control API.

Provides endpoints to start/stop the captive portal and manage
the displayed alert from your teammate's web dashboard.
"""

import json
import os
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

from .schemas import (
    PortalStartRequest,
    PortalStatusResponse,
    PortalUpdateRequest,
    StatusResponse,
)
from .portal_manager import get_portal_manager

router = APIRouter(prefix="/api/portal", tags=["Captive Portal"])

# Alerts directory (shared with alert_router)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALERTS_DIR = _PROJECT_ROOT / "alerts"


def _load_alert_for_portal(alert_id: str) -> dict:
    """Load alert metadata and convert to portal display format."""
    meta_path = ALERTS_DIR / f"{alert_id}.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    severity = meta.get("severity", "Extreme")

    severity_colors = {
        "Extreme": "#CC0000",
        "Severe": "#E65100",
        "Moderate": "#E6A800",
        "Minor": "#2E7D32",
        "Unknown": "#555555",
    }

    title_map = {
        "Extreme": "EXTREME FLOOD ALERT",
        "Severe": "SEVERE FLOOD ALERT",
        "Moderate": "FLOOD WARNING",
        "Minor": "FLOOD ADVISORY",
    }

    return {
        "title": title_map.get(severity, "FLOOD ALERT"),
        "headline": meta.get("headline", "Flood Alert"),
        "severity": severity,
        "urgency": meta.get("urgency", "Immediate"),
        "area_desc": meta.get("village", "Affected area"),
        "instruction": meta.get("instruction", "Follow local authority guidance."),
        "description": meta.get("description", ""),
        "sender": meta.get("sender", "AAPDA SETU Gateway"),
        "timestamp": meta.get("timestamp", ""),
        "bg_color": severity_colors.get(severity, "#CC0000"),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/start", response_model=StatusResponse)
async def start_portal(req: PortalStartRequest):
    """Start the Wi-Fi captive portal.

    Launches the DNS interceptor and web server in background threads.
    Requires the Windows Mobile Hotspot to be enabled and DNS redirected.
    See docs/setup_captive_portal.md for laptop setup.
    """
    manager = get_portal_manager()

    if manager.is_active:
        raise HTTPException(status_code=409, detail="Portal is already running")

    # Load alert data
    alert_data = None
    if req.alert_id:
        alert_data = _load_alert_for_portal(req.alert_id)
    elif req.text:
        alert_data = {
            "title": "EMERGENCY ALERT",
            "headline": req.text[:100],
            "instruction": req.text,
        }

    result = manager.start(
        hotspot_ip=req.hotspot_ip,
        dns_port=req.dns_port,
        web_port=req.web_port,
        alert_data=alert_data,
    )

    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])

    return StatusResponse(status="ok", message=result["message"])


@router.post("/stop", response_model=StatusResponse)
async def stop_portal():
    """Stop the captive portal."""
    manager = get_portal_manager()

    if not manager.is_active:
        raise HTTPException(status_code=409, detail="Portal is not running")

    result = manager.stop()
    return StatusResponse(status="ok", message=result["message"])


@router.get("/status", response_model=PortalStatusResponse)
async def portal_status():
    """Get the current captive portal status and connected device count."""
    manager = get_portal_manager()
    status = manager.status()

    return PortalStatusResponse(
        active=status["active"],
        hotspot_ip=status.get("hotspot_ip"),
        unique_devices=status.get("unique_devices", 0),
        total_hits=status.get("total_hits", 0),
        alert_headline=status.get("alert_headline"),
        alert_severity=status.get("alert_severity"),
        started_at=status.get("started_at"),
    )


@router.post("/update-alert", response_model=StatusResponse)
async def update_portal_alert(req: PortalUpdateRequest):
    """Update the alert displayed on a running captive portal.

    Use this to push new prediction data to the portal without restarting.
    """
    manager = get_portal_manager()

    if not manager.is_active:
        raise HTTPException(status_code=409, detail="Portal is not running")

    # Build update dict from non-None fields
    update_data = {k: v for k, v in req.model_dump().items() if v is not None}

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = manager.update_alert(update_data)
    return StatusResponse(status="ok", message=result["message"])


@router.post("/trigger-trapdoor", response_model=StatusResponse)
async def trigger_portal_trapdoor():
    """Activate the trapdoor: enable DNS hijack and bounce Windows Mobile Hotspot."""
    manager = get_portal_manager()
    result = manager.trigger_trapdoor()
    return StatusResponse(
        status=result.get("status", "ok"),
        message=result.get("message", "Trapdoor activated and hotspot bounced."),
    )


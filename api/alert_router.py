"""Alert Router — CAP Alert Generation & Management API.

Wraps cap_builder.py into FastAPI endpoints. Your teammate's prediction
model calls POST /api/alerts/generate when it detects a flood.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

# Add cap-generator to Python path so we can import cap_builder
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CAP_GEN_DIR = _PROJECT_ROOT / "cap-generator"
if str(_CAP_GEN_DIR) not in sys.path:
    sys.path.insert(0, str(_CAP_GEN_DIR))

from cap_builder import CAPBuilder  # noqa: E402

from .schemas import (
    AlertRequest,
    AlertResponse,
    AlertSummary,
    AlertListResponse,
)

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])

# Storage directory for generated alerts
ALERTS_DIR = _PROJECT_ROOT / "alerts"
ALERTS_DIR.mkdir(exist_ok=True)


def _load_alert_meta(alert_id: str) -> Optional[dict]:
    """Load alert metadata JSON from disk."""
    meta_path = ALERTS_DIR / f"{alert_id}.json"
    if not meta_path.exists():
        return None
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_alert_meta(alert_id: str, meta: dict):
    """Save alert metadata JSON to disk."""
    meta_path = ALERTS_DIR / f"{alert_id}.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/generate", response_model=AlertResponse)
async def generate_alert(req: AlertRequest):
    """Generate a CAP 1.2 XML alert from flood prediction data.

    This is the main integration point. Your teammate's prediction model
    calls this endpoint when it detects dangerous water levels.

    Returns the alert ID, CAP XML, and BLE-ready short text.
    """
    # Build CAP alert using existing CAPBuilder
    builder = CAPBuilder(sender=req.sender, status=req.status)

    desc = req.description or f"Flood warning for {req.village}."

    builder.add_info(
        event="Flood",
        urgency=req.urgency,
        severity=req.severity,
        certainty=req.certainty,
        headline=f"Flood Alert for {req.village}",
        description=desc,
        instruction=req.instruction,
        areas=[{
            "areaDesc": req.village,
            "circles": [(req.lat, req.lon, req.radius)],
        }],
    )

    # Validate
    errors = builder.validate()
    if errors:
        raise HTTPException(status_code=422, detail={"validation_errors": errors})

    # Generate outputs
    alert_id = builder.identifier
    cap_xml = builder.to_xml_string()
    short_text = builder.to_short_text()

    ist = timezone(timedelta(hours=5, minutes=30))
    timestamp = datetime.now(ist).strftime("%d %b %Y, %H:%M IST")

    # Save XML file
    xml_filename = f"alert_{req.village}_{alert_id[:8]}.xml".replace(" ", "_")
    xml_path = ALERTS_DIR / xml_filename
    builder.save_xml(str(xml_path))

    # Save metadata for later retrieval
    meta = {
        "alert_id": alert_id,
        "headline": f"Flood Alert for {req.village}",
        "severity": req.severity,
        "urgency": req.urgency,
        "certainty": req.certainty,
        "village": req.village,
        "lat": req.lat,
        "lon": req.lon,
        "radius": req.radius,
        "instruction": req.instruction,
        "description": desc,
        "status": req.status,
        "timestamp": timestamp,
        "short_text": short_text,
        "xml_file": xml_filename,
        "sender": req.sender,
    }
    _save_alert_meta(alert_id, meta)

    return AlertResponse(
        alert_id=alert_id,
        cap_xml=cap_xml,
        short_text=short_text,
        headline=f"Flood Alert for {req.village}",
        severity=req.severity,
        village=req.village,
        timestamp=timestamp,
        xml_file_path=str(xml_path),
    )


@router.get("/", response_model=AlertListResponse)
async def list_alerts(
    limit: int = Query(50, ge=1, le=200),
    severity: Optional[str] = Query(None, description="Filter by severity"),
):
    """List all generated alerts, newest first."""
    alerts = []
    for meta_file in sorted(ALERTS_DIR.glob("*.json"), reverse=True):
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)

        if severity and meta.get("severity") != severity:
            continue

        alerts.append(AlertSummary(
            alert_id=meta["alert_id"],
            headline=meta["headline"],
            severity=meta["severity"],
            village=meta["village"],
            timestamp=meta["timestamp"],
            status=meta["status"],
        ))

        if len(alerts) >= limit:
            break

    return AlertListResponse(alerts=alerts, total=len(alerts))


@router.get("/{alert_id}")
async def get_alert(alert_id: str, format: str = Query("json", enum=["json", "xml"])):
    """Get a specific alert by ID. Returns JSON metadata or raw CAP XML."""
    meta = _load_alert_meta(alert_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    if format == "xml":
        xml_path = ALERTS_DIR / meta["xml_file"]
        if not xml_path.exists():
            raise HTTPException(status_code=404, detail="XML file not found")
        xml_content = xml_path.read_text(encoding="utf-8")
        return Response(content=xml_content, media_type="application/xml")

    return meta


@router.get("/{alert_id}/short-text")
async def get_short_text(alert_id: str):
    """Get the BLE-ready short text for an alert (for mesh broadcast)."""
    meta = _load_alert_meta(alert_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    return {"alert_id": alert_id, "short_text": meta.get("short_text", "")}

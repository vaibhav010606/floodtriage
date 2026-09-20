"""Pydantic schemas for the CAP Alert System API.

These models define the request/response contracts that your teammate's
Next.js frontend and FastAPI prediction backend will use.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Alert Schemas
# ---------------------------------------------------------------------------

class AlertRequest(BaseModel):
    """Request body for POST /api/alerts/generate.

    Your teammate's prediction model sends this when it detects a flood.
    """
    village: str = Field(..., description="Village or area name", examples=["Majuli"])
    lat: float = Field(..., description="Center latitude", examples=[26.95])
    lon: float = Field(..., description="Center longitude", examples=[94.17])
    radius: float = Field(5.0, description="Alert radius in km")
    severity: str = Field("Extreme", description="Extreme/Severe/Moderate/Minor")
    urgency: str = Field("Immediate", description="Immediate/Expected/Future")
    certainty: str = Field("Likely", description="Observed/Likely/Possible/Unlikely")
    instruction: str = Field(
        ...,
        description="Actionable instruction for people",
        examples=["Move to higher ground immediately"],
    )
    description: Optional[str] = Field(
        None, description="Detailed description (auto-generated if omitted)"
    )
    status: str = Field("Actual", description="'Test' or 'Actual'")
    sender: str = Field(
        "flood-authority@cap-mesh-gateway.local",
        description="Sender identifier",
    )


class AlertResponse(BaseModel):
    """Response from POST /api/alerts/generate."""
    alert_id: str
    cap_xml: str
    short_text: str
    headline: str
    severity: str
    village: str
    timestamp: str
    xml_file_path: str


class AlertSummary(BaseModel):
    """Summary of a stored alert for listing."""
    alert_id: str
    headline: str
    severity: str
    village: str
    timestamp: str
    status: str


class AlertListResponse(BaseModel):
    """Response from GET /api/alerts/."""
    alerts: list[AlertSummary]
    total: int


# ---------------------------------------------------------------------------
# Gateway (BLE Broadcast) Schemas
# ---------------------------------------------------------------------------

class BroadcastRequest(BaseModel):
    """Request body for POST /api/gateway/broadcast."""
    alert_id: Optional[str] = Field(
        None, description="ID of a saved alert to broadcast"
    )
    text: Optional[str] = Field(
        None, description="Raw text to broadcast (if no alert_id)"
    )
    nickname: str = Field("FloodGateway", description="Gateway nickname on mesh")
    dry_run: bool = Field(False, description="Build packet but don't send")


class BroadcastResponse(BaseModel):
    """Response from POST /api/gateway/broadcast."""
    success: bool
    message: str
    packet_size_bytes: Optional[int] = None
    devices_reached: Optional[int] = None


class GatewayStatusResponse(BaseModel):
    """Response from GET /api/gateway/status."""
    ble_available: bool
    message: str


# ---------------------------------------------------------------------------
# Captive Portal Schemas
# ---------------------------------------------------------------------------

class PortalStartRequest(BaseModel):
    """Request body for POST /api/portal/start."""
    alert_id: Optional[str] = Field(
        None, description="Use a saved alert for the portal page"
    )
    text: Optional[str] = Field(
        None, description="Custom alert text (if no alert_id)"
    )
    hotspot_ip: str = Field("192.168.137.1", description="Hotspot adapter IP")
    dns_port: int = Field(53, description="DNS interceptor port")
    web_port: int = Field(80, description="Web server port")


class PortalStatusResponse(BaseModel):
    """Response from GET /api/portal/status."""
    active: bool
    hotspot_ip: Optional[str] = None
    unique_devices: int = 0
    total_hits: int = 0
    alert_headline: Optional[str] = None
    alert_severity: Optional[str] = None
    started_at: Optional[str] = None


class PortalUpdateRequest(BaseModel):
    """Request body for POST /api/portal/update-alert."""
    title: Optional[str] = None
    headline: Optional[str] = None
    severity: Optional[str] = None
    urgency: Optional[str] = None
    area_desc: Optional[str] = None
    instruction: Optional[str] = None
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# Generic
# ---------------------------------------------------------------------------

class StatusResponse(BaseModel):
    """Generic status response."""
    status: str
    message: str

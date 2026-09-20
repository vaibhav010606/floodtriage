"""Example: How to mount CAP system routers into your FastAPI app.

YOUR TEAMMATE: Copy the relevant lines into your existing main.py.
This file also works as a standalone server for testing.

Usage:
    pip install fastapi uvicorn
    uvicorn api.app_mount_example:app --reload --port 8000

Then open: http://localhost:8000/docs  (Swagger UI)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ===========================================================================
# YOUR TEAMMATE: Add these 3 imports to your existing FastAPI app
# ===========================================================================
from api.alert_router import router as alert_router
from api.gateway_router import router as gateway_router
from api.portal_router import router as portal_router

# ===========================================================================
# Create FastAPI app (your teammate already has this)
# ===========================================================================
app = FastAPI(
    title="AAPDA SETU - Flood Alert System",
    description=(
        "Flood prediction trigger -> CAP 1.2 alert -> "
        "BLE mesh broadcast + Wi-Fi captive portal.\n\n"
        "**Alert API**: Generate and manage CAP alerts\n"
        "**Gateway API**: Broadcast alerts over Bluetooth mesh\n"
        "**Portal API**: Control the Wi-Fi captive portal"
    ),
    version="1.0.0",
)

# CORS — allow Next.js frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",     # Next.js dev server
        "http://127.0.0.1:3000",
        "http://localhost:5173",     # Vite dev server
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===========================================================================
# YOUR TEAMMATE: Add these 3 lines to mount the CAP routers
# ===========================================================================
app.include_router(alert_router)
app.include_router(gateway_router)
app.include_router(portal_router)

# ===========================================================================
# Example: Your teammate's prediction endpoint triggering an alert
# ===========================================================================

@app.get("/")
async def root():
    return {
        "service": "AAPDA SETU Flood Alert System",
        "docs": "/docs",
        "endpoints": {
            "alerts": "/api/alerts/",
            "gateway": "/api/gateway/status",
            "portal": "/api/portal/status",
        },
    }


@app.post("/api/predict/trigger-alert")
async def prediction_triggers_alert():
    """EXAMPLE: How the prediction model would trigger a full alert cycle.

    Your teammate's prediction model would call this flow:
    1. Generate a CAP alert
    2. Broadcast over BLE mesh
    3. Start the captive portal

    This is an example — your teammate would replace this with their
    actual prediction logic.
    """
    import httpx

    # Step 1: Generate alert from prediction data
    # (In practice, your teammate calls alert_router directly or via HTTP)
    from api.alert_router import generate_alert
    from api.schemas import AlertRequest

    alert_req = AlertRequest(
        village="Majuli",
        lat=26.95,
        lon=94.17,
        radius=5.0,
        severity="Extreme",
        urgency="Immediate",
        certainty="Observed",
        instruction="Water levels rising rapidly. Move to higher ground immediately.",
        description="AAPDA SETU prediction model detected critical water levels "
                    "at Majuli Island. Expected flooding within 2 hours.",
        status="Actual",
    )

    alert_resp = await generate_alert(alert_req)

    return {
        "message": "Alert generated from prediction",
        "alert_id": alert_resp.alert_id,
        "headline": alert_resp.headline,
        "short_text": alert_resp.short_text,
        "next_steps": {
            "broadcast_ble": f"POST /api/gateway/broadcast with alert_id={alert_resp.alert_id}",
            "start_portal": f"POST /api/portal/start with alert_id={alert_resp.alert_id}",
        },
    }

"""Portal Manager — Programmatic control of the Wi-Fi Captive Portal.

This module wraps captive_portal.py's functionality into a class that
can be started/stopped from FastAPI endpoints or any Python code.
"""

import json
import logging
import os
import socket
import sys
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

log = logging.getLogger("portal_manager")

# Add gateway to path for imports
_GATEWAY_DIR = Path(__file__).resolve().parent.parent / "gateway"
if str(_GATEWAY_DIR) not in sys.path:
    sys.path.insert(0, str(_GATEWAY_DIR))


class PortalManager:
    """Manages the captive portal DNS + HTTP servers lifecycle.

    Usage:
        manager = PortalManager()
        manager.start(hotspot_ip="192.168.137.1", alert_data={...})
        manager.status()
        manager.update_alert({...})
        manager.stop()
    """

    _instance: Optional["PortalManager"] = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton — only one portal can run at a time."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._active = False
        self._dns_thread: Optional[threading.Thread] = None
        self._http_thread: Optional[threading.Thread] = None
        self._dns_socket: Optional[socket.socket] = None
        self._http_server = None
        self._hotspot_ip: Optional[str] = None
        self._started_at: Optional[str] = None

        # Import portal state from captive_portal module
        self._portal_module = None

    def _ensure_portal_module(self):
        """Lazy import the captive_portal module."""
        if self._portal_module is None:
            try:
                import captive_portal as cp
                self._portal_module = cp
            except ImportError:
                raise RuntimeError(
                    "captive_portal module not found. Ensure gateway/ is in Python path."
                )
        return self._portal_module

    def start(
        self,
        hotspot_ip: str = "192.168.137.1",
        dns_port: int = 53,
        web_port: int = 80,
        alert_data: Optional[dict] = None,
    ) -> dict:
        """Start the captive portal (DNS interceptor + web server).

        Args:
            hotspot_ip: The hotspot adapter's IPv4 address.
            dns_port: Port for the DNS interceptor (default 53).
            web_port: Port for the Flask web server (default 80).
            alert_data: Optional dict with alert fields to display.

        Returns:
            Status dict with success/error information.
        """
        if self._active:
            return {"status": "already_running", "message": "Portal is already active"}

        cp = self._ensure_portal_module()

        # Update alert data if provided
        if alert_data:
            cp.update_alert(alert_data)

        self._hotspot_ip = hotspot_ip

        # Start DNS server thread
        self._dns_thread = threading.Thread(
            target=cp.run_dns_server,
            args=(hotspot_ip, dns_port),
            daemon=True,
            name="portal-dns",
        )
        self._dns_thread.start()

        # Give DNS a moment to bind
        time.sleep(0.3)

        # Start Flask in a background thread using werkzeug server
        app = cp.create_flask_app()

        try:
            from werkzeug.serving import make_server
            self._http_server = make_server("0.0.0.0", web_port, app, threaded=True)
        except Exception as e:
            return {"status": "error", "message": f"Cannot bind port {web_port}: {e}"}

        self._http_thread = threading.Thread(
            target=self._http_server.serve_forever,
            daemon=True,
            name="portal-http",
        )
        self._http_thread.start()

        self._active = True
        ist = timezone(timedelta(hours=5, minutes=30))
        self._started_at = datetime.now(ist).strftime("%d %b %Y, %H:%M IST")

        log.info(
            "Captive portal started: DNS=%s:%d, HTTP=%s:%d",
            hotspot_ip, dns_port, "0.0.0.0", web_port,
        )

        return {
            "status": "started",
            "message": f"Portal active on {hotspot_ip}",
            "hotspot_ip": hotspot_ip,
            "dns_port": dns_port,
            "web_port": web_port,
        }

    def stop(self) -> dict:
        """Stop the captive portal."""
        if not self._active:
            return {"status": "not_running", "message": "Portal is not active"}

        # Stop HTTP server
        if self._http_server:
            try:
                self._http_server.shutdown()
            except Exception as e:
                log.warning("Error stopping HTTP server: %s", e)
            self._http_server = None

        self._active = False
        self._started_at = None
        log.info("Captive portal stopped")

        return {"status": "stopped", "message": "Portal stopped successfully"}

    def status(self) -> dict:
        """Get current portal status."""
        cp = self._ensure_portal_module()

        if not self._active:
            return {
                "active": False,
                "unique_devices": 0,
                "total_hits": 0,
            }

        alert = cp.get_alert_data()
        return {
            "active": True,
            "hotspot_ip": self._hotspot_ip,
            "unique_devices": alert.get("device_count", 0),
            "total_hits": cp._device_tracker.get("total_hits", 0),
            "alert_headline": alert.get("headline", ""),
            "alert_severity": alert.get("severity", ""),
            "started_at": self._started_at,
        }

    def update_alert(self, data: dict) -> dict:
        """Update the displayed alert on a running portal."""
        cp = self._ensure_portal_module()
        cp.update_alert(data)
        return {"status": "ok", "message": "Alert updated"}

    def trigger_trapdoor(self) -> dict:
        """Activate the trapdoor: enable DNS hijack and bounce Windows Mobile Hotspot."""
        cp = self._ensure_portal_module()
        return cp.trigger_trapdoor()

    @property
    def is_active(self) -> bool:
        return self._active


# Module-level singleton accessor
def get_portal_manager() -> PortalManager:
    """Get the singleton PortalManager instance."""
    return PortalManager()

#!/usr/bin/env python3
"""Wi-Fi Captive Portal — Emergency Flood Alert Gateway Node.

Turns a Windows laptop into an emergency Wi-Fi gateway that broadcasts
flood alerts to ANY nearby phone/device via a captive portal. Works
alongside the existing BLE mesh broadcast channel.

Architecture:
    1. DNS Interceptor (Port 53): Hijacks all DNS queries → hotspot IP
    2. Flask Web Server (Port 80): Serves the emergency alert HTML page
    3. Captive Portal Detection: Auto-triggers popup on iOS/Android/Windows

Prerequisites:
    - Windows Mobile Hotspot enabled (SSID: !_EMERGENCY_FLOOD_ALERT_!)
    - Hotspot adapter DNS set to 127.0.0.1
    - Run as Administrator (needs Port 53 + 80)
    - See docs/setup_captive_portal.md for full setup guide

Usage:
    python captive_portal.py
    python captive_portal.py --cap-file alert.xml
    python captive_portal.py --text "FLOOD ALERT: Evacuate immediately"
    python captive_portal.py --dry-run
"""

import argparse
import json
import logging
import os
import socket
import sys
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

import yaml

try:
    from dnslib import DNSRecord, RR, QTYPE, A
    HAS_DNSLIB = True
except ImportError:
    HAS_DNSLIB = False

try:
    from flask import Flask, request, render_template, jsonify
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("captive_portal")

# ---------------------------------------------------------------------------
# Default alert data (used when no CAP file or --text is provided)
# ---------------------------------------------------------------------------
DEFAULT_ALERT = {
    "title": "⚠️ EXTREME FLOOD ALERT ⚠️",
    "headline": "EVACUATE IMMEDIATELY",
    "severity": "Extreme",
    "urgency": "Immediate",
    "area_desc": "Nearby flood-prone area",
    "instruction": "Critical water levels predicted by AAPDA SETU models. "
                   "Move to high ground now. Do not attempt to cross flooded roads.",
    "description": "Automated flood prediction models have detected dangerous "
                   "water level rise. This alert is being broadcast via emergency "
                   "Wi-Fi gateway to all nearby devices.",
    "sender": "AAPDA SETU Emergency Gateway",
    "timestamp": "",
    "bg_color": "#CC0000",
}

# Map CAP severity to background color
SEVERITY_COLORS = {
    "Extreme": "#CC0000",   # Deep red
    "Severe": "#E65100",    # Dark orange
    "Moderate": "#E6A800",  # Amber
    "Minor": "#2E7D32",     # Green
    "Unknown": "#555555",   # Grey
}

# ---------------------------------------------------------------------------
# Global mutable alert state (can be updated via API)
# ---------------------------------------------------------------------------
_alert_lock = threading.Lock()
_current_alert = dict(DEFAULT_ALERT)
_device_tracker = {"unique_ips": set(), "total_hits": 0}


def get_alert_data():
    """Return a snapshot of the current alert data."""
    with _alert_lock:
        data = dict(_current_alert)
        data["device_count"] = len(_device_tracker["unique_ips"])
        if not data["timestamp"]:
            ist = timezone(timedelta(hours=5, minutes=30))
            data["timestamp"] = datetime.now(ist).strftime("%d %b %Y, %H:%M IST")
        return data


def update_alert(new_data: dict):
    """Update the current alert data."""
    with _alert_lock:
        _current_alert.update(new_data)
        log.info("Alert data updated: %s", new_data.get("headline", "(no headline)"))


def track_device(ip: str):
    """Track a unique device connection."""
    with _alert_lock:
        _device_tracker["total_hits"] += 1
        is_new = ip not in _device_tracker["unique_ips"]
        _device_tracker["unique_ips"].add(ip)
        if is_new:
            count = len(_device_tracker["unique_ips"])
            log.info("[+] New device connected: %s (total unique: %d)", ip, count)


# ---------------------------------------------------------------------------
# CAP XML Parser — extract alert data from existing CAP generator output
# ---------------------------------------------------------------------------
CAP_NS = "urn:oasis:names:tc:emergency:cap:1.2"


def parse_cap_file(filepath: str) -> dict:
    """Parse a CAP 1.2 XML file and extract alert fields for the portal."""
    if not os.path.exists(filepath):
        log.error("CAP file not found: %s", filepath)
        sys.exit(1)

    tree = ET.parse(filepath)
    root = tree.getroot()
    ns = {"cap": CAP_NS}

    sender = root.findtext("cap:sender", default="Unknown", namespaces=ns)
    sent_raw = root.findtext("cap:sent", default="", namespaces=ns)

    # Parse the sent timestamp for display
    timestamp_display = sent_raw
    if sent_raw:
        try:
            dt = datetime.fromisoformat(sent_raw)
            timestamp_display = dt.strftime("%d %b %Y, %H:%M IST")
        except ValueError:
            pass

    info = root.find("cap:info", ns)
    if info is None:
        log.warning("CAP file has no <info> block, using defaults")
        return {"sender": sender, "timestamp": timestamp_display}

    severity = info.findtext("cap:severity", default="Unknown", namespaces=ns)
    urgency = info.findtext("cap:urgency", default="Unknown", namespaces=ns)
    headline = info.findtext("cap:headline", default="Flood Alert", namespaces=ns)
    description = info.findtext("cap:description", default="", namespaces=ns)
    instruction = info.findtext("cap:instruction", default="Follow local authority guidance.", namespaces=ns)
    event = info.findtext("cap:event", default="Flood", namespaces=ns)

    # Extract area description
    area = info.find("cap:area", ns)
    area_desc = "Affected area"
    if area is not None:
        area_desc = area.findtext("cap:areaDesc", default="Affected area", namespaces=ns)

    bg_color = SEVERITY_COLORS.get(severity, "#CC0000")

    title_map = {
        "Extreme": "⚠️ EXTREME FLOOD ALERT ⚠️",
        "Severe": "🔴 SEVERE FLOOD ALERT",
        "Moderate": "🟠 FLOOD WARNING",
        "Minor": "🟡 FLOOD ADVISORY",
    }
    title = title_map.get(severity, f"⚠️ {event.upper()} ALERT")

    return {
        "title": title,
        "headline": headline,
        "severity": severity,
        "urgency": urgency,
        "area_desc": area_desc,
        "instruction": instruction,
        "description": description,
        "sender": sender,
        "timestamp": timestamp_display,
        "bg_color": bg_color,
    }


# ---------------------------------------------------------------------------
# DNS Interceptor Server (Port 53)
# ---------------------------------------------------------------------------
TRAPDOOR_ACTIVE = False

def trigger_trapdoor():
    """Activate the trapdoor: enable DNS hijack and bounce the Windows Mobile Hotspot."""
    global TRAPDOOR_ACTIVE
    TRAPDOOR_ACTIVE = True
    log.info("[!!!] TRAPDOOR ACTIVATED [!!!]")
    log.info("DNS Hijack is now LIVE. Redirection enabled.")
    log.info("Bouncing Windows Mobile Hotspot to force pop-ups on connected phones...")
    
    import subprocess
    ps_cmd = (
        "$profiles = [Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]::GetConnectionProfiles(); "
        "foreach ($p in $profiles) { "
        "  $m = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]::CreateFromConnectionProfile($p); "
        "  if ($m.TetheringOperationalState -eq 'On') { "
        "    $m.StopTetheringAsync(); Start-Sleep -Seconds 3; $m.StartTetheringAsync(); break "
        "  } "
        "}"
    )
    try:
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
        log.info("Hotspot restarted successfully! Phones should trigger captive portal.")
        return {"status": "ok", "message": "Trapdoor triggered and hotspot bounced"}
    except Exception as e:
        log.error("Could not auto-restart hotspot: %s", e)
        return {"status": "error", "message": str(e)}

def run_dns_server(hotspot_ip: str, port: int = 53):
    """UDP DNS server that responds to ALL queries with the hotspot IP.

    This hijacks every DNS lookup from connected phones so they all
    resolve to our Flask web server, triggering the captive portal.
    """
    if not HAS_DNSLIB:
        log.error("dnslib not installed. Run: pip install dnslib")
        return

    try:
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_sock.bind(("0.0.0.0", port))
    except PermissionError:
        log.error("Cannot bind to port %d — run as Administrator!", port)
        return
    except OSError as e:
        if "10048" in str(e) or "address already in use" in str(e).lower():
            log.error(
                "Port %d already in use. Windows ICS may be holding it.\n"
                "  Fix: Set hotspot adapter DNS to 127.0.0.1\n"
                "  See: docs/setup_captive_portal.md Step 3", port
            )
        else:
            log.error("DNS bind error: %s", e)
        return

    log.info("[*] DNS Interceptor running on 0.0.0.0:%d → all queries → %s", port, hotspot_ip)

    while True:
        try:
            data, addr = udp_sock.recvfrom(1024)
            req = DNSRecord.parse(data)
            
            if not TRAPDOOR_ACTIVE:
                # PASSIVE MODE: Give a fake public IP so the phone tries to connect to the real internet.
                # Since it has no internet, the request will time out silently without popping up the captive portal!
                reply = req.reply()
                reply.add_answer(RR(req.q.qname, QTYPE.A, rdata=A("8.8.8.8"), ttl=60))
                udp_sock.sendto(reply.pack(), addr)
                continue

            reply = req.reply()

            qname = str(req.q.qname)

            # Respond to ALL queries with the hotspot IP
            reply.add_answer(
                RR(req.q.qname, QTYPE.A, rdata=A(hotspot_ip), ttl=60)
            )

            udp_sock.sendto(reply.pack(), addr)
            log.debug("DNS: %s → %s (from %s)", qname, hotspot_ip, addr[0])

        except Exception as e:
            log.debug("DNS error: %s", e)


# ---------------------------------------------------------------------------
# Flask Web Server (Port 80) — Captive Portal
# ---------------------------------------------------------------------------
def create_flask_app():
    """Create and configure the Flask application."""
    # Set template folder relative to this script
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
    app = Flask(__name__, template_folder=template_dir)

    # Suppress Flask's default request logging (we do our own)
    flask_log = logging.getLogger("werkzeug")
    flask_log.setLevel(logging.WARNING)

    # ------------------------------------------------------------------
    # Captive Portal Detection Endpoints
    # These are the URLs that Android, iOS, and Windows probe to detect
    # internet connectivity. By returning specific responses, we trigger
    # the native captive portal popup.
    # ------------------------------------------------------------------

    # Android connectivity checks
    @app.route("/generate_204")
    @app.route("/gen_204")
    def android_check():
        track_device(request.remote_addr)
        # Return 302 redirect to trigger Android's captive portal popup
        return "", 302, {"Location": f"http://{request.host}/"}

    @app.route("/connectivitycheck.gstatic.com/generate_204")
    def android_check_full():
        track_device(request.remote_addr)
        return "", 302, {"Location": f"http://{request.host}/"}

    # Apple/iOS connectivity checks
    @app.route("/hotspot-detect.html")
    @app.route("/library/test/success.html")
    def apple_check():
        track_device(request.remote_addr)
        # iOS expects non-"Success" response to trigger captive portal
        alert = get_alert_data()
        return render_template("emergency_alert.html", **alert)

    # Windows connectivity checks
    @app.route("/connecttest.txt")
    @app.route("/ncsi.txt")
    def windows_check():
        track_device(request.remote_addr)
        return "", 302, {"Location": f"http://{request.host}/"}

    @app.route("/redirect")
    def windows_redirect():
        track_device(request.remote_addr)
        return "", 302, {"Location": f"http://{request.host}/"}

    # ------------------------------------------------------------------
    # Main alert page & catch-all
    # ------------------------------------------------------------------
    @app.route("/")
    def index():
        track_device(request.remote_addr)
        alert = get_alert_data()
        return render_template("emergency_alert.html", **alert)

    @app.route("/safe-zones")
    def safe_zones():
        """Placeholder for safe zones map — future Phase 7+ integration."""
        track_device(request.remote_addr)
        return """<!DOCTYPE html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>body{background:#1a1a2e;color:white;font-family:sans-serif;text-align:center;padding:40px;}
h1{margin-bottom:20px;}a{color:#4fc3f7;}</style></head>
<body><h1>🗺️ Safe Zones</h1>
<p>Safe zone map data will be available in a future update.</p>
<p>For now, move to the <strong>nearest high ground</strong> or <strong>concrete building above ground floor</strong>.</p>
<p><a href="/">← Back to Alert</a></p></body></html>""", 200

    # ------------------------------------------------------------------
    # Live API — update alert without restarting
    # ------------------------------------------------------------------
    @app.route("/api/update-alert", methods=["POST"])
    def api_update_alert():
        """Update the displayed alert via POST request.

        Useful for piping new CAP alerts into a running portal.
        Only accepts requests from localhost for security.
        """
        if request.remote_addr not in ("127.0.0.1", "::1"):
            return jsonify({"error": "Forbidden — localhost only"}), 403

        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "No JSON body"}), 400

        update_alert(data)
        return jsonify({"status": "ok", "alert": get_alert_data()})

    @app.route("/api/status")
    def api_status():
        """Return current portal status — device count, alert info."""
        alert = get_alert_data()
        return jsonify({
            "status": "active",
            "unique_devices": alert["device_count"],
            "total_hits": _device_tracker["total_hits"],
            "alert_headline": alert["headline"],
            "alert_severity": alert["severity"],
        })

    @app.route("/api/trigger-trapdoor", methods=["POST"])
    def api_trigger_trapdoor():
        """Trigger the trapdoor and bounce hotspot via API."""
        if request.remote_addr not in ("127.0.0.1", "::1", "192.168.137.1"):
            return jsonify({"error": "Forbidden — localhost only"}), 403
        data = request.get_json(silent=True) or {}
        if data:
            update_alert(data)
        res = trigger_trapdoor()
        return jsonify({"status": "ok", "trapdoor": res, "alert": get_alert_data()})

    # ------------------------------------------------------------------
    # Catch-all: redirect ANY other URL to the alert page
    # ------------------------------------------------------------------
    @app.route("/<path:path>")
    def catch_all(path):
        track_device(request.remote_addr)
        # Return 302 redirect for most paths to consolidate on root
        return "", 302, {"Location": f"http://{request.host}/"}

    return app


# ---------------------------------------------------------------------------
# Configuration loader
# ---------------------------------------------------------------------------
def load_portal_config(config_path: str) -> dict:
    """Load captive portal settings from the gateway config.yaml."""
    defaults = {
        "hotspot_ip": "192.168.137.1",
        "dns_port": 53,
        "web_port": 80,
        "hotspot_ssid": "!_EMERGENCY_FLOOD_ALERT_!",
    }

    if not os.path.exists(config_path):
        return defaults

    with open(config_path, "r") as f:
        config = yaml.safe_load(f) or {}

    portal_config = config.get("captive_portal", {})
    defaults.update(portal_config)
    return defaults


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="AAPDA SETU — Wi-Fi Captive Portal Emergency Gateway",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python captive_portal.py                              # Default alert
  python captive_portal.py --cap-file alert.xml         # From CAP XML
  python captive_portal.py --text "EVACUATE NOW"        # Quick text
  python captive_portal.py --hotspot-ip 192.168.137.1   # Custom IP
  python captive_portal.py --dry-run                    # Test without binding
        """,
    )
    parser.add_argument(
        "--config", default="config.yaml",
        help="Path to gateway config.yaml (default: config.yaml)"
    )
    parser.add_argument(
        "--cap-file",
        help="Path to CAP 1.2 XML alert file (from generate_alert.py)"
    )
    parser.add_argument(
        "--text",
        help="Quick custom alert text (headline + instruction)"
    )
    parser.add_argument(
        "--hotspot-ip",
        help="Override hotspot IP (default: from config or 192.168.137.1)"
    )
    parser.add_argument(
        "--web-port", type=int,
        help="Override web server port (default: 80)"
    )
    parser.add_argument(
        "--dns-port", type=int,
        help="Override DNS server port (default: 53)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate configuration and exit without binding ports"
    )
    args = parser.parse_args()

    # Check dependencies
    missing = []
    if not HAS_DNSLIB:
        missing.append("dnslib")
    if not HAS_FLASK:
        missing.append("flask")
    if missing:
        log.error("Missing dependencies: %s", ", ".join(missing))
        log.error("Install with: pip install %s", " ".join(missing))
        sys.exit(1)

    # Load config
    config_path = args.config
    if not os.path.isabs(config_path):
        # Look relative to this script's directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        candidate = os.path.join(script_dir, config_path)
        if os.path.exists(candidate):
            config_path = candidate

    portal_config = load_portal_config(config_path)

    # CLI overrides
    hotspot_ip = args.hotspot_ip or portal_config["hotspot_ip"]
    dns_port = args.dns_port or portal_config["dns_port"]
    web_port = args.web_port or portal_config["web_port"]
    ssid = portal_config["hotspot_ssid"]

    # Populate alert data from source
    if args.cap_file:
        cap_data = parse_cap_file(args.cap_file)
        update_alert(cap_data)
        log.info("Loaded alert from CAP file: %s", args.cap_file)
    elif args.text:
        update_alert({
            "title": "⚠️ EMERGENCY ALERT ⚠️",
            "headline": args.text[:100],
            "instruction": args.text,
        })
        log.info("Using custom text alert")
    else:
        log.info("Using default alert template")

    # Set timestamp if not already set
    ist = timezone(timedelta(hours=5, minutes=30))
    with _alert_lock:
        if not _current_alert["timestamp"]:
            _current_alert["timestamp"] = datetime.now(ist).strftime(
                "%d %b %Y, %H:%M IST"
            )

    # Print banner
    print()
    print("=" * 60)
    print("  AAPDA SETU - Emergency Wi-Fi Captive Portal")
    print("=" * 60)
    print(f"  Hotspot SSID : {ssid}")
    print(f"  Hotspot IP   : {hotspot_ip}")
    print(f"  DNS Server   : 0.0.0.0:{dns_port}")
    print(f"  Web Server   : 0.0.0.0:{web_port}")
    print(f"  Alert        : {_current_alert['headline']}")
    print("=" * 60)
    print()

    if args.dry_run:
        print("[DRY RUN] Configuration valid. Checking template...")
        app = create_flask_app()
        with app.test_client() as client:
            resp = client.get("/")
            if resp.status_code == 200:
                print("[DRY RUN] [OK] Alert page renders correctly")
                print(f"[DRY RUN]      Page size: {len(resp.data)} bytes")
            else:
                print(f"[DRY RUN] [FAIL] Alert page error: HTTP {resp.status_code}")
                sys.exit(1)

            resp = client.get("/api/status")
            if resp.status_code == 200:
                print("[DRY RUN] [OK] Status API responds correctly")
            else:
                print(f"[DRY RUN] [FAIL] Status API error: HTTP {resp.status_code}")

        print("\n[DRY RUN] All checks passed. Ready for live deployment.")
        print("[DRY RUN] Run without --dry-run as Administrator to go live.")
        sys.exit(0)

    # Start DNS server in background thread
    dns_thread = threading.Thread(
        target=run_dns_server,
        args=(hotspot_ip, dns_port),
        daemon=True,
        name="dns-interceptor",
    )
    dns_thread.start()

    # Give DNS thread a moment to bind
    time.sleep(0.5)

    def trapdoor_listener():
        print("\n" + "="*60)
        print(" [TRAPDOOR] System is in PASSIVE mode.")
        print(" [TRAPDOOR] Press ENTER to ACTIVATE the Emergency Alert...")
        print("="*60 + "\n")
        try:
            input()
        except:
            pass
        trigger_trapdoor()
        print("\n" + "!"*60)
        print(" [!!!] TRAPDOOR ACTIVATED [!!!]")
        print("!"*60 + "\n")

    trapdoor_thread = threading.Thread(
        target=trapdoor_listener,
        daemon=True,
        name="trapdoor-listener"
    )
    trapdoor_thread.start()

    # Start Flask web server (this blocks)
    log.info("[*] Captive Portal ACTIVE — SSID: %s", ssid)
    log.info("[*] Waiting for device connections...")
    log.info("[*] Press Ctrl+C to stop\n")

    app = create_flask_app()
    try:
        app.run(host="0.0.0.0", port=web_port, debug=False, threaded=True)
    except PermissionError:
        log.error(
            "Cannot bind to port %d — run as Administrator!\n"
            "  Right-click Command Prompt → 'Run as administrator'", web_port
        )
        sys.exit(1)
    except OSError as e:
        if "10048" in str(e) or "address already in use" in str(e).lower():
            log.error("Port %d already in use. Stop the conflicting service first.", web_port)
        else:
            log.error("Web server error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()

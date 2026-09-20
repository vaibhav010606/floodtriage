# 🌊 Flood CAP Alert System

Flood-prediction trigger → CAP 1.2 alert → Bluetooth mesh broadcast.
People with no cellular or internet signal still get the warning, phone to phone.

---

## 📌 Overview

During severe flood events, cellular towers and power infrastructure frequently fail, leaving downstream and remote riverine communities cut off from conventional emergency communication. The **Flood CAP Alert System** solves this critical last-mile problem by bridging automated standard emergency alerts into an off-grid device-to-device mesh network.

- **What It Does**: Ingests flood alerts or trigger events, structures them according to OASIS Common Alerting Protocol (CAP v1.2), cryptographically signs the message, and transmits the payload directly over a local Bluetooth Low Energy (BLE) mesh network powered by the [bitchat-android](https://github.com/permissionlesstech/bitchat-android) protocol. Additionally, a **Wi-Fi Captive Portal** mode turns a laptop into an emergency gateway that broadcasts alerts to **any nearby phone** — even those without the AAPDA SETU app.
- **Architecture Flow**:
  1. **Python CAP Generator**: Generates OASIS CAP 1.2 compliant flood alert XML documents.
  2. **Ed25519-Signed Gateway**: Converts CAP alerts into compact BitChat-compatible broadcast packets and signs them.
  3. **BLE Mesh Transport**: Broadcasts packets hop-by-hop over Bluetooth LE (up to 7 hops, offline peer-to-peer).
  4. **Modified Android Client**: Listens on the mesh, validates the gateway signature, and presents an unmissable full-screen emergency alert UI with siren audio.
  5. **Wi-Fi Captive Portal** *(NEW)*: Laptop creates a Wi-Fi hotspot that hijacks DNS and forces an emergency alert page onto any connecting phone's screen — no app installation required.
- **Protocol Foundation**: Built on `bitchat-android`'s decentralized protocol, utilizing Bluetooth Low Energy peer discovery, a multi-hop flood/gossip routing algorithm (maximum 7 hops), and Noise Protocol cryptographic primitives.

---

## 📂 Project Structure

```
cap/
├── bitchat-android/          # Cloned mesh app repo
├── cap-generator/            # Python CAP 1.2 alert generator
│   ├── cap_builder.py        # CAPBuilder class
│   ├── generate_alert.py     # CLI tool
│   ├── example_alerts/       # Reference CAP XML files
│   └── tests/
├── gateway/                  # BLE mesh broadcast gateway
│   ├── keygen.py             # Ed25519 keypair generator
│   ├── packet.py             # BitChat wire protocol builder
│   ├── gateway.py            # Main gateway script (BLE mesh)
│   ├── captive_portal.py     # Wi-Fi captive portal server (DNS + HTTP)
│   ├── templates/
│   │   └── emergency_alert.html  # Mobile-optimized alert page
│   └── config.yaml
├── docs/                     # Reference docs & field test logs
│   ├── field_test_log.md     # Standardized field testing template
│   ├── rollout_plan.md       # Community distribution & deployment plan
│   └── setup_captive_portal.md  # Laptop setup guide for captive portal
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10 or higher
- Bluetooth 4.2+ compatible BLE adapter (for live gateway broadcast)
- Android 8.0+ devices (for mesh receiving and relaying)

```bash
# Prerequisites & Dependencies
python --version  # 3.10+
pip install -r cap-generator/requirements.txt
pip install -r gateway/requirements.txt

# Phase 2: Look at the reference CAP alert
cat cap-generator/example_alerts/sample_flood_alert.xml

# Phase 3: Generate a CAP alert
python cap-generator/generate_alert.py \
  --village "Majuli" --lat 26.95 --lon 94.17 --radius 5.0 \
  --severity Extreme --instruction "Move to higher ground immediately"

# Phase 5: Generate gateway keys
python gateway/keygen.py

# Phase 5: Broadcast an alert (requires Bluetooth adapter)
python gateway/gateway.py --text "FLOOD ALERT: Majuli — river rising. Move to higher ground. 08:30 IST"

# Or dry-run without Bluetooth:
python gateway/gateway.py --dry-run --text "FLOOD ALERT: Test message"

# Run tests
python -m pytest cap-generator/tests/ -v

# Phase 10: Wi-Fi Captive Portal (see docs/setup_captive_portal.md)
pip install dnslib flask
python gateway/captive_portal.py --dry-run          # Test without binding ports
python gateway/captive_portal.py                     # Run as Admin for live mode
python gateway/captive_portal.py --cap-file alert.xml  # Use a CAP alert file
```

### 🚨 Trapdoor Mode (Delayed Wi-Fi Hijack)
The Captive Portal now includes an interactive **Trapdoor Mode** that forces the emergency alert to appear on command:
1. Run `python gateway/captive_portal.py` as Administrator.
2. The system starts in **PASSIVE mode**. Phones can connect silently without triggering the captive portal pop-up (the script serves a dummy IP to bypass OS connectivity checks).
3. When you are ready to broadcast the alert, press **`Enter`** in the terminal.
4. The script instantly activates the DNS hijack and automatically bounces the Windows Mobile Hotspot using a background PowerShell script.
5. Connected devices are forced to auto-reconnect, instantly triggering the full-screen Emergency Flood Warning pop-up on their screens!

### 🆘 SOS Dispatch System (FloodTriage Integration)

The SOS Dispatch System connects the **FloodTriage** flood-prediction dashboard to the CAP Alert broadcast pipeline — when a simulation or ML prediction detects a critical flood threat, it can push a real emergency alert directly to nearby phones through **all three channels simultaneously**.

#### How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│  FloodTriage Dashboard (Next.js frontend on port 3000)         │
│                                                                 │
│  User adjusts simulation parameters or runs ML prediction       │
│       ↓                                                         │
│  🚨 "DISPATCH CAP SOS TO PHONES" button appears                │
│       ↓  POST /api/sos/dispatch                                 │
└────────┬────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  SOS Dispatcher Service (sos_dispatcher.py)                     │
│                                                                 │
│  1. Generates OASIS CAP 1.2 XML alert with flood details        │
│  2. Triggers Wi-Fi Captive Portal trapdoor (DNS hijack)         │
│  3. Broadcasts via BLE BitChat mesh (background thread)         │
└─────────────────────────────────────────────────────────────────┘
         │
         ├──→ 📡 Channel 1: Wi-Fi Captive Portal
         │       Bounces the hotspot, forces all connected phones
         │       to see the full-screen emergency alert page.
         │
         ├──→ 📡 Channel 2: BLE BitChat Mesh
         │       Broadcasts Ed25519-signed CAP packet over
         │       Bluetooth LE (up to 7 hops, fully offline).
         │
         └──→ 📡 Channel 3: Web UI Alert Panel
                 In-app notification on the FloodTriage dashboard
                 with success/error status feedback.
```

#### API Endpoint

```
POST /api/sos/dispatch
```

| Parameter     | Type   | Default                     | Description                                                  |
| :------------ | :----- | :-------------------------- | :----------------------------------------------------------- |
| `hazard_level`| string | `"Critical Threat"`         | Severity label (e.g., `Critical Threat`, `Warning`)          |
| `water_level` | float  | `15.0`                      | Predicted water level in meters                              |
| `threshold`   | float  | `10.0`                      | Danger threshold in meters                                   |
| `village`     | string | `"Majuli"`                  | Target area / village name                                   |
| `lat`         | float  | `26.95`                     | Latitude of affected area                                    |
| `lon`         | float  | `94.17`                     | Longitude of affected area                                   |
| `instruction` | string | `"Move to higher ground…"`  | Emergency instruction for residents                          |

**Response:**
```json
{
  "status": "success",
  "alert_id": "urn:oid:2.49.0.0.356.0.2025.0920.103045",
  "message": "SOS dispatched via 3 channels",
  "channels": {
    "cap_xml": true,
    "wifi_portal": true,
    "ble_mesh": true
  }
}
```

#### Auto-Trigger on Critical Predictions

The SOS system also fires **automatically** in two scenarios:

1. **ML Prediction** (`POST /api/ml/predict-river-stage`):
   When the model predicts `hazard_level == "Critical Threat"`, the SOS is dispatched automatically alongside the prediction response.

2. **Hydraulic Simulation** (`POST /api/simulation/run`):
   When simulated river levels breach the critical station thresholds, the SOS is triggered and the response includes `sos_dispatched: true`.

#### Quick Start — Manual SOS Dispatch

```bash
# 1. Start the FloodTriage backend (port 8000)
cd floodtriage/backend
uvicorn app.main:app --reload --port 8000

# 2. Start the Captive Portal (port 80 + DNS on port 53, requires Admin)
python gateway/captive_portal.py

# 3. Fire a manual SOS via curl
curl -X POST http://localhost:8000/api/sos/dispatch \
  -H "Content-Type: application/json" \
  -d '{"village": "Majuli", "water_level": 15.0, "threshold": 10.0}'

# Or use the dashboard UI:
# Open http://localhost:3000 → River Stage Forecaster → click the red
# "🚨 DISPATCH CAP SOS TO PHONES" button.
```

#### Key Files

| File | Purpose |
| :--- | :--- |
| `floodtriage/backend/app/services/sos_dispatcher.py` | Core dispatch service — generates CAP XML, triggers Wi-Fi trapdoor, launches BLE broadcast |
| `floodtriage/backend/app/api/endpoints/sos.py` | REST endpoint `POST /api/sos/dispatch` |
| `floodtriage/frontend/components/ML/RiverStageForecaster.tsx` | UI panel with the SOS dispatch button |
| `gateway/captive_portal.py` | Wi-Fi captive portal with `/api/trigger-trapdoor` route |
| `gateway/gateway.py` | BLE mesh broadcast engine |

---

## 🗺️ Project Phases

| Phase | Description | Status |
| :--- | :--- | :---: |
| **Phase 0: Prerequisites & Project Scaffolding** | Repository structure, architecture specifications, dependencies, and environment setup. | ✅ |
| **Phase 1: Prove Mesh Network Operation** | Clone `bitchat-android`, build baseline APK, and verify basic multi-hop peer delivery between test phones. | 🔲 |
| **Phase 2: Hand-Build Reference CAP Alert** | Construct and validate an OASIS CAP v1.2 flood alert XML file adhering to national alerting standards. | ✅ |
| **Phase 3: Automate CAP Generation** | Implement `CAPBuilder` and `generate_alert.py` CLI supporting flexible geometries, urgency, and instructions. | ✅ |
| **Phase 4: Manual Trigger & Dispatch Interface** | Provide emergency operator trigger scripts and test runners for instant CAP dispatch. | ✅ |
| **Phase 5: Build Gateway & BLE Broadcast Bridge** | Wire protocol packing (`packet.py`), Ed25519 signing (`keygen.py`), and Bleak BLE broadcast engine (`gateway.py`). | ✅ *(code ready, needs BLE testing)* |
| **Phase 6: Android App Customization & Alert UI** | Modify `bitchat-android` to parse CAP flood packets, verify gateway signatures, and display full-screen alert UI. | 🔲 |
| **Phase 7: Localized Multi-Lingual Alerting & TTS** | Implement multi-language warning text (Assamese, Hindi, etc.) and offline audio alert syntheses. | 🔲 |
| **Phase 8: Field Testing & Mesh Density Benchmarks** | Conduct range, propagation latency, battery impact, and obstruction tests in flood-vulnerable field zones. | 🔲 |
| **Phase 9: Deployment, Seed Node Rollout & SDMA Integration** | Deploy solar-backed community gateways, execute community seed node distribution, and coordinate with DDMA/SDMA. | 🔲 |
| **Phase 10: Wi-Fi Captive Portal Emergency Gateway** | Turn any laptop into a Wi-Fi gateway that broadcasts flood alerts to all nearby phones via captive portal — no app needed. | ✅ |
| **Phase 11: SOS Dispatch System (FloodTriage)** | Unified SOS dispatch connecting ML predictions and hydraulic simulations to all alert channels (CAP XML → Wi-Fi Portal + BLE Mesh + Web UI). | ✅ |

---

## 📄 License

This project is dedicated to the public domain under [The Unlicense](https://unlicense.org/) (matching `bitchat-android`'s public domain dedication), or alternately under the MIT License at the user's discretion.

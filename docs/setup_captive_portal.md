# 📡 Captive Portal — Laptop Setup Guide

This guide walks you through the **one-time manual configuration** required on your Windows laptop before running the captive portal script. These steps turn your laptop into an emergency Wi-Fi gateway node.

---

## Prerequisites

- Windows 10/11 laptop with Wi-Fi adapter
- Python 3.10+ installed
- Administrator access on the laptop
- Dependencies installed: `pip install -r gateway/requirements.txt`

---

## Step 1: Enable Windows Mobile Hotspot

1. Open **Settings** → **Network & Internet** → **Mobile hotspot**
2. Turn **ON** the Mobile hotspot toggle
3. Click **Edit** and configure:
   - **Network name**: `!_EMERGENCY_FLOOD_ALERT_!`
   - **Network password**: Remove/clear the password (open network)
   - **Network band**: 2.4 GHz (better range for emergencies)
4. Click **Save**

> **Why an open network?** During flood emergencies, victims need instant access without asking for passwords. The portal only serves alert information — no sensitive data passes through.

> **Why that SSID?** The `!` prefix makes it sort to the top of available Wi-Fi networks on most phones, and the name itself communicates urgency even before connecting.

---

## Step 2: Find Your Hotspot IP Address

1. Press `Win + R`, type `cmd`, press Enter
2. Run: `ipconfig`
3. Look for the adapter named **"Local Area Connection\* ..."** or **"Wireless LAN adapter Local Area Connection\*"** — this is your hotspot adapter
4. Note the **IPv4 Address** — it's usually `192.168.137.1`

```
Wireless LAN adapter Local Area Connection* 10:

   Connection-specific DNS Suffix  . :
   IPv4 Address. . . . . . . . . . . : 192.168.137.1   ← THIS ONE
   Subnet Mask . . . . . . . . . . . : 255.255.255.0
```

If your IP is different from `192.168.137.1`, update `gateway/config.yaml`:
```yaml
captive_portal:
  hotspot_ip: "YOUR_ACTUAL_IP"
```

---

## Step 3: Redirect Hotspot DNS to Your Script

Windows Internet Connection Sharing (ICS) runs its own DNS server on Port 53, which will block the Python DNS interceptor. You must override the hotspot adapter's DNS settings.

1. Press `Win + R`, type `ncpa.cpl`, press Enter
2. Find the adapter named **"Local Area Connection\* ..."** (your active hotspot)
3. **Right-click** → **Properties**
4. Select **Internet Protocol Version 4 (TCP/IPv4)** → click **Properties**
5. Select **"Use the following DNS server addresses"**
6. Set **Preferred DNS server** to: `127.0.0.1`
7. Leave **Alternate DNS server** blank
8. Click **OK** → **OK**

> ⚠️ **Important**: You must do this EVERY time you restart the hotspot, as Windows may reset these settings.

---

## Step 4: Allow Ports Through Windows Firewall

The script needs Port 53 (DNS) and Port 80 (HTTP). Create firewall rules:

### Option A: Quick Command (run as Administrator)

```powershell
# Allow DNS (Port 53 UDP inbound)
netsh advfirewall firewall add rule name="AAPDA SETU - DNS" dir=in action=allow protocol=UDP localport=53

# Allow HTTP (Port 80 TCP inbound)
netsh advfirewall firewall add rule name="AAPDA SETU - HTTP" dir=in action=allow protocol=TCP localport=80
```

### Option B: Manual via Windows Defender Firewall

1. Open **Windows Defender Firewall with Advanced Security**
2. Click **Inbound Rules** → **New Rule**
3. Select **Port** → **UDP** → Specific port: `53` → **Allow** → Name: `AAPDA SETU - DNS`
4. Repeat for **TCP** port `80` → Name: `AAPDA SETU - HTTP`

---

## Step 5: Launch the Captive Portal

Open **Command Prompt as Administrator**:

```powershell
# Navigate to your project
cd c:\Users\vaibh\OneDrive\Desktop\cap

# Run the captive portal
python gateway/captive_portal.py
```

With a CAP alert file:
```powershell
python gateway/captive_portal.py --cap-file alert_Majuli_20260920_1030.xml
```

With custom text:
```powershell
python gateway/captive_portal.py --text "EXTREME FLOOD: Majuli island. Evacuate to high ground immediately."
```

You should see:
```
[*] DNS Interceptor running on 0.0.0.0:53
[*] Web Server running on 0.0.0.0:80
[*] Captive Portal ACTIVE — SSID: !_EMERGENCY_FLOOD_ALERT_!
[*] Waiting for device connections...
```

---

## Step 6: Test with Your Phone

1. On your phone, go to **Wi-Fi settings**
2. Connect to `!_EMERGENCY_FLOOD_ALERT_!`
3. The emergency alert page should **automatically pop up** as a captive portal notification
4. If it doesn't pop up automatically, open any browser and navigate to any website — you'll be redirected to the alert page

---

## Troubleshooting

### "Port 53 already in use"
Windows ICS is still holding Port 53. Solutions:
1. Make sure you completed **Step 3** (redirect DNS to 127.0.0.1)
2. Restart the hotspot (turn off → on again)
3. Run in admin CMD: `net stop SharedAccess` then `net start SharedAccess`

### "Port 80 already in use"
Another service (like IIS or Skype) is using Port 80.
1. Find the process: `netstat -ano | findstr :80`
2. Kill it: `taskkill /PID <PID> /F`
3. Or use an alternate port: `python captive_portal.py --web-port 8080`

### Phone doesn't show captive portal popup
- **Android**: Open browser, go to `http://192.168.137.1` manually
- **iOS**: Wait 5-10 seconds after connecting; iOS checks `http://captive.apple.com`
- **Samsung**: Try opening `http://connectivitycheck.gstatic.com/generate_204`

### Hotspot keeps disconnecting
- Plug in your laptop charger (power saving can disable hotspot)
- Disable "Turn off hotspot automatically when no devices are connected" in hotspot settings

---

## Cleanup After Emergency

1. Stop the script with `Ctrl+C`
2. Remove the firewall rules:
   ```powershell
   netsh advfirewall firewall delete rule name="AAPDA SETU - DNS"
   netsh advfirewall firewall delete rule name="AAPDA SETU - HTTP"
   ```
3. Reset the hotspot adapter DNS back to "Obtain DNS server address automatically"
4. Turn off Mobile Hotspot

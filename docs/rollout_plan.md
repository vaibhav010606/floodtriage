# Rollout Plan — Flood Alert Mesh Network

## Target Area
- Village/District: [TBD]
- Population: [TBD]
- Flood risk season: June–October

## Phase 1: Seed Network (5–10 devices)

### Seed Node Selection
Identify 3–5 trusted community members:
- [ ] Panchayat member / village head
- [ ] School teacher
- [ ] Shop owner (central location)
- [ ] Health worker (ANM/ASHA)
- [ ] Religious institution caretaker

### Installation Process
1. Meet each seed node in person
2. Install modified APK via Bluetooth/Quick Share (no internet needed)
3. Walk through the app — show them what a normal message vs flood alert looks like
4. Explain: "Keep Bluetooth on, keep app running in background"
5. Give them a printed one-page guide in local language

## Phase 2: Community Spread (10–50 devices)
Each seed node shares the APK with 5–10 contacts using bitchat's built-in sharing.

## Phase 3: Always-On Gateway
- [ ] Set up dedicated device (old Android phone or Raspberry Pi) at community hub
- Location options: school, temple/mosque/church, panchayat office, health center
- Requirements: power supply, Bluetooth range to nearby homes
- The gateway runs `MeshForegroundService` 24/7

## Phase 4: Redundancy
- [ ] Pair with loudspeaker/siren system
- [ ] SMS fallback where cellular signal exists
- [ ] Printed emergency procedure posted at community hub
- [ ] Contact local SDMA/DDMA for coordination

## APK Sharing Security
bitchat-android verifies APK certificate fingerprint (`BITCHAT_GITHUB_RELEASE_CERT_SHA256` in gradle.properties) before installation. Update this value in your forked build.

## Success Metrics
- [ ] ≥80% of households in target area have at least one phone with the app
- [ ] Alert delivery within 5 minutes across the network
- [ ] ≥90% of test users understand the alert and know what to do
- [ ] Battery drain <5% per hour with app in background

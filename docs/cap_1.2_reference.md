# CAP 1.2 Quick Reference Cheat Sheet

This document serves as a quick reference for the Common Alerting Protocol (CAP) Version 1.2.

## 1. XML Structure Overview

```text
<alert> (1)
  ├── identifier (1)
  ├── sender (1)
  ├── sent (1)
  ├── status (1)
  ├── msgType (1)
  ├── source (0..1)
  ├── scope (1)
  ├── restriction (0..1)
  ├── addresses (0..1)
  ├── code (0..*)
  ├── note (0..1)
  ├── references (0..1)
  ├── incidents (0..1)
  └── <info> (0..*)
        ├── language (0..1)
        ├── category (1..*)
        ├── event (1)
        ├── responseType (0..*)
        ├── urgency (1)
        ├── severity (1)
        ├── certainty (1)
        ├── audience (0..1)
        ├── eventCode (0..*)
        ├── effective (0..1)
        ├── onset (0..1)
        ├── expires (0..1)
        ├── senderName (0..1)
        ├── headline (0..1)
        ├── description (0..1)
        ├── instruction (0..1)
        ├── web (0..1)
        ├── contact (0..1)
        ├── parameter (0..*)
        ├── <resource> (0..*)
        └── <area> (0..*)
              ├── areaDesc (1)
              ├── polygon (0..*)
              ├── circle (0..*)
              ├── geocode (0..*)
              ├── altitude (0..1)
              └── ceiling (0..1)
```

## 2. Required Fields

### `<alert>` Level
| Element | Required | Description |
| :--- | :--- | :--- |
| `identifier` | Yes | Unique identifier for the alert |
| `sender` | Yes | Identifier of the sender |
| `sent` | Yes | Date and time the alert was sent (ISO 8601) |
| `status` | Yes | Code denoting the appropriate handling |
| `msgType` | Yes | Code denoting the nature of the message |
| `scope` | Yes | Code denoting the intended audience |

### `<info>` Level (If `<info>` is present)
| Element | Required | Description |
| :--- | :--- | :--- |
| `category` | Yes (1 or more) | Code denoting the category of the subject event |
| `event` | Yes | Text denoting the type of the subject event |
| `urgency` | Yes | Code denoting the urgency of the subject event |
| `severity` | Yes | Code denoting the severity of the subject event |
| `certainty` | Yes | Code denoting the certainty of the subject event |

### `<area>` Level (If `<area>` is present)
| Element | Required | Description |
| :--- | :--- | :--- |
| `areaDesc` | Yes | Text describing the affected area |

## 3. Enumerations

| Element | Valid Values |
| :--- | :--- |
| **`status`** | `Actual`, `Exercise`, `System`, `Test`, `Draft` |
| **`msgType`** | `Alert`, `Update`, `Cancel`, `Ack`, `Error` |
| **`scope`** | `Public`, `Restricted`, `Private` |
| **`urgency`** | `Immediate`, `Expected`, `Future`, `Past`, `Unknown` |
| **`severity`** | `Extreme`, `Severe`, `Moderate`, `Minor`, `Unknown` |
| **`certainty`** | `Observed`, `Likely`, `Possible`, `Unlikely`, `Unknown` |
| **`category`** | `Geo`, `Met`, `Safety`, `Security`, `Rescue`, `Fire`, `Health`, `Env`, `Transport`, `Infra`, `CBRNE`, `Other` |
| **`responseType`** | `Shelter`, `Evacuate`, `Prepare`, `Execute`, `Avoid`, `Monitor`, `Assess`, `AllClear`, `None` |

## 4. Geographic Formats

| Type | Format | Example |
| :--- | :--- | :--- |
| **Circle** | `latitude,longitude,radius_in_km` | `26.95,94.17,10.0` |
| **Polygon** | Space-separated `latitude,longitude` pairs. First and last pair must match. | `26.98,94.12 27.02,94.20 26.95,94.25 26.88,94.15 26.98,94.12` |

## 5. India-Specific Implementations

### LGD Geocodes
Use `<geocode>` in the `<area>` block to specify Local Government Directory (LGD) codes.
```xml
<geocode>
  <valueName>LGD_STATE_CODE</valueName>
  <value>18</value>
</geocode>
```

### SACHET 4-Tier Color Matrix
SACHET uses Urgency + Severity to map alerts to colors:

| Color | Urgency | Severity | Meaning |
| :--- | :--- | :--- | :--- |
| **Red** | Immediate / Expected | Extreme / Severe | Take Action |
| **Orange** | Expected / Future | Severe / Moderate | Be Prepared |
| **Yellow** | Future | Moderate / Minor | Be Updated |
| **Green** | Past / Unknown | Minor / Unknown | No Warning |

*(Note: Exact mappings can vary by agency, but this is the general framework).*

### SACHET Feed URL
The national SACHET CAP alert feed is typically available at:
`https://sachet.ndma.gov.in/cap_public_website/cap/getcaplist`

## 6. Conditional Requirements

| Element | Required When | Description |
| :--- | :--- | :--- |
| **`restriction`** | `scope` is `Restricted` | Text describing the rule for limiting distribution. |
| **`addresses`** | `scope` is `Private` | Space separated list of recipient addresses. |
| **`references`** | `msgType` is `Update` or `Cancel` | Space separated list of identifiers for earlier alerts that are referenced. |

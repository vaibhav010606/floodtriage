"""CAP 1.2 XML Builder for Flood Alert System.

Generates OASIS Common Alerting Protocol v1.2 compliant XML alerts
and condensed short text suitable for Bluetooth mesh broadcast.
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid
from xml.dom import minidom

CAP_NS = "urn:oasis:names:tc:emergency:cap:1.2"

VALID_STATUS = ("Actual", "Exercise", "System", "Test", "Draft")
VALID_MSG_TYPE = ("Alert", "Update", "Cancel", "Ack", "Error")
VALID_SCOPE = ("Public", "Restricted", "Private")
VALID_URGENCY = ("Immediate", "Expected", "Future", "Past", "Unknown")
VALID_SEVERITY = ("Extreme", "Severe", "Moderate", "Minor", "Unknown")
VALID_CERTAINTY = ("Observed", "Likely", "Possible", "Unlikely", "Unknown")
VALID_CATEGORY = ("Geo", "Met", "Safety", "Security", "Rescue", "Fire", "Health", "Env", "Transport", "Infra", "CBRNE", "Other")
VALID_RESPONSE_TYPE = ("Shelter", "Evacuate", "Prepare", "Execute", "Avoid", "Monitor", "Assess", "AllClear", "None")

class CAPBuilder:
    def __init__(self, sender: str, status="Actual", msg_type="Alert", scope="Public"):
        self.sender = sender
        self.status = status
        self.msg_type = msg_type
        self.scope = scope
        self.identifier = str(uuid.uuid4())
        
        ist_offset = timezone(timedelta(hours=5, minutes=30))
        self.sent = datetime.now(ist_offset)
        self.info_blocks = []

    def add_info(self, event, urgency, severity, certainty, headline, description, instruction, areas: list[dict], language="en-IN", sender_name="", expires_hours=12, response_type="Prepare", category="Met"):
        expires = self.sent + timedelta(hours=expires_hours)
        info = {
            "event": event,
            "urgency": urgency,
            "severity": severity,
            "certainty": certainty,
            "headline": headline,
            "description": description,
            "instruction": instruction,
            "areas": areas,
            "language": language,
            "sender_name": sender_name,
            "expires": expires,
            "response_type": response_type,
            "category": category
        }
        self.info_blocks.append(info)

    def to_xml(self) -> ET.Element:
        ET.register_namespace("", CAP_NS)
        root = ET.Element(f"{{{CAP_NS}}}alert")
        
        ET.SubElement(root, f"{{{CAP_NS}}}identifier").text = self.identifier
        ET.SubElement(root, f"{{{CAP_NS}}}sender").text = self.sender
        
        sent_str = self.sent.isoformat(timespec='seconds')
        ET.SubElement(root, f"{{{CAP_NS}}}sent").text = sent_str
        
        ET.SubElement(root, f"{{{CAP_NS}}}status").text = self.status
        ET.SubElement(root, f"{{{CAP_NS}}}msgType").text = self.msg_type
        ET.SubElement(root, f"{{{CAP_NS}}}scope").text = self.scope

        for info_data in self.info_blocks:
            info = ET.SubElement(root, f"{{{CAP_NS}}}info")
            ET.SubElement(info, f"{{{CAP_NS}}}language").text = info_data["language"]
            ET.SubElement(info, f"{{{CAP_NS}}}category").text = info_data["category"]
            ET.SubElement(info, f"{{{CAP_NS}}}event").text = info_data["event"]
            if info_data["response_type"]:
                ET.SubElement(info, f"{{{CAP_NS}}}responseType").text = info_data["response_type"]
            ET.SubElement(info, f"{{{CAP_NS}}}urgency").text = info_data["urgency"]
            ET.SubElement(info, f"{{{CAP_NS}}}severity").text = info_data["severity"]
            ET.SubElement(info, f"{{{CAP_NS}}}certainty").text = info_data["certainty"]
            
            ET.SubElement(info, f"{{{CAP_NS}}}expires").text = info_data["expires"].isoformat(timespec='seconds')
            if info_data["sender_name"]:
                ET.SubElement(info, f"{{{CAP_NS}}}senderName").text = info_data["sender_name"]
            ET.SubElement(info, f"{{{CAP_NS}}}headline").text = info_data["headline"]
            ET.SubElement(info, f"{{{CAP_NS}}}description").text = info_data["description"]
            ET.SubElement(info, f"{{{CAP_NS}}}instruction").text = info_data["instruction"]

            for area_data in info_data["areas"]:
                area = ET.SubElement(info, f"{{{CAP_NS}}}area")
                ET.SubElement(area, f"{{{CAP_NS}}}areaDesc").text = area_data.get("areaDesc", "Unknown Area")
                
                for poly in area_data.get("polygons", []):
                    poly_str = " ".join([f"{lat},{lon}" for lat, lon in poly])
                    ET.SubElement(area, f"{{{CAP_NS}}}polygon").text = poly_str
                    
                for lat, lon, radius in area_data.get("circles", []):
                    ET.SubElement(area, f"{{{CAP_NS}}}circle").text = f"{lat},{lon} {radius}"
                    
                for name, value in area_data.get("geocodes", []):
                    gc = ET.SubElement(area, f"{{{CAP_NS}}}geocode")
                    ET.SubElement(gc, f"{{{CAP_NS}}}valueName").text = name
                    ET.SubElement(gc, f"{{{CAP_NS}}}value").text = value
                    
        return root

    def to_xml_bytes(self) -> bytes:
        root = self.to_xml()
        xml_str = ET.tostring(root, encoding="utf-8")
        parsed = minidom.parseString(xml_str)
        return parsed.toprettyxml(indent="  ", encoding="utf-8")

    def to_xml_string(self) -> str:
        return self.to_xml_bytes().decode("utf-8")

    def to_short_text(self) -> str:
        if not self.info_blocks:
            return "FLOOD ALERT"
        
        info = self.info_blocks[0]
        desc = info["description"][:50].strip()
        instr = info["instruction"][:50].strip()
        time_str = self.sent.strftime("%H:%M IST")
        
        areas = info["areas"]
        village = areas[0].get("areaDesc", "Unknown") if areas else "Unknown"
        
        text = f"FLOOD ALERT: {village} - {desc}. {instr}. [{time_str}]"
        while len(text.encode("utf-8")) > 200:
            desc = desc[:-2]
            text = f"FLOOD ALERT: {village} - {desc}.. {instr}. [{time_str}]"
        return text

    def validate(self) -> list[str]:
        errors = []
        if not self.identifier: errors.append("Missing identifier")
        if not self.sender: errors.append("Missing sender")
        if not self.sent: errors.append("Missing sent")
        
        if self.status not in VALID_STATUS: errors.append(f"Invalid status: {self.status}")
        if self.msg_type not in VALID_MSG_TYPE: errors.append(f"Invalid msgType: {self.msg_type}")
        if self.scope not in VALID_SCOPE: errors.append(f"Invalid scope: {self.scope}")
        
        if not self.info_blocks:
            errors.append("At least one <info> block is required")
            
        for idx, info in enumerate(self.info_blocks):
            if info["category"] not in VALID_CATEGORY: errors.append(f"Info[{idx}]: Invalid category {info['category']}")
            if not info["event"]: errors.append(f"Info[{idx}]: Missing event")
            if info["urgency"] not in VALID_URGENCY: errors.append(f"Info[{idx}]: Invalid urgency {info['urgency']}")
            if info["severity"] not in VALID_SEVERITY: errors.append(f"Info[{idx}]: Invalid severity {info['severity']}")
            if info["certainty"] not in VALID_CERTAINTY: errors.append(f"Info[{idx}]: Invalid certainty {info['certainty']}")
            
            for area_idx, area in enumerate(info["areas"]):
                if "areaDesc" not in area or not area["areaDesc"]:
                    errors.append(f"Info[{idx}] Area[{area_idx}]: Missing areaDesc")
                for poly_idx, poly in enumerate(area.get("polygons", [])):
                    if not poly or poly[0] != poly[-1]:
                        errors.append(f"Info[{idx}] Area[{area_idx}] Polygon[{poly_idx}]: First and last coordinates must match")
                        
        return errors

    def save_xml(self, filepath: str):
        """Write the CAP XML to a file."""
        with open(filepath, "wb") as f:
            f.write(self.to_xml_bytes())

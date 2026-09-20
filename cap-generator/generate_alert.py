import argparse
from datetime import datetime
from cap_builder import CAPBuilder
import sys

def main():
    parser = argparse.ArgumentParser(description="Generate CAP 1.2 Flood Alert")
    parser.add_argument("--village", required=True, help="Village/area name")
    parser.add_argument("--lat", required=True, type=float, help="Center latitude")
    parser.add_argument("--lon", required=True, type=float, help="Center longitude")
    parser.add_argument("--radius", default=5.0, type=float, help="Radius in km")
    parser.add_argument("--severity", default="Severe", help="Extreme/Severe/Moderate/Minor")
    parser.add_argument("--urgency", default="Immediate", help="Immediate/Expected/Future")
    parser.add_argument("--certainty", default="Likely", help="Observed/Likely/Possible")
    parser.add_argument("--instruction", required=True, help="Actionable instruction text")
    parser.add_argument("--description", help="Detailed description (auto-generated if omitted)")
    parser.add_argument("--sender", default="flood-authority@cap-mesh-gateway.local")
    parser.add_argument("--output", help="Output filename")
    parser.add_argument("--status", default="Test", help="Test or Actual")
    parser.add_argument("--expires-hours", default=12, type=int)

    args = parser.parse_args()

    desc = args.description or f"Flood warning for {args.village}."
    
    builder = CAPBuilder(sender=args.sender, status=args.status)
    builder.add_info(
        event="Flood",
        urgency=args.urgency,
        severity=args.severity,
        certainty=args.certainty,
        headline=f"Flood Alert for {args.village}",
        description=desc,
        instruction=args.instruction,
        areas=[{"areaDesc": args.village, "circles": [(args.lat, args.lon, args.radius)]}],
        expires_hours=args.expires_hours
    )

    errors = builder.validate()
    print("Validation Errors:", errors if errors else "None")

    out_file = args.output
    if not out_file:
        time_str = datetime.now().strftime("%Y%m%d_%H%M")
        out_file = f"alert_{args.village}_{time_str}.xml".replace(" ", "_")

    builder.save_xml(out_file)
    print(f"XML saved to {out_file}")
    
    print("\nShort Text for BLE Broadcast:")
    print(builder.to_short_text())

if __name__ == "__main__":
    main()

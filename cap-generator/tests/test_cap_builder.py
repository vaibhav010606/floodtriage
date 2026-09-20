import unittest
from cap_builder import CAPBuilder
import xml.etree.ElementTree as ET

class TestCAPBuilder(unittest.TestCase):
    def test_basic_alert_generation(self):
        builder = CAPBuilder(sender="test@test.com")
        builder.add_info("Flood", "Immediate", "Severe", "Likely", "Headline", "Desc", "Inst", [{"areaDesc": "Test Area"}])
        xml_str = builder.to_xml_string()
        self.assertIn("urn:oasis:names:tc:emergency:cap:1.2", xml_str)
        self.assertIn("<identifier>", xml_str)
        self.assertIn("<sender>test@test.com</sender>", xml_str)

    def test_multiple_severities(self):
        for sev in ["Extreme", "Severe", "Moderate", "Minor"]:
            builder = CAPBuilder(sender="test@test.com")
            builder.add_info("Flood", "Immediate", sev, "Likely", "Headline", "Desc", "Inst", [{"areaDesc": "Area"}])
            self.assertEqual(len(builder.validate()), 0)

    def test_multiple_villages(self):
        villages = [("Majuli", 26.95, 94.17), ("Dhemaji", 27.48, 94.58), ("Lakhimpur", 27.23, 94.10), ("Sivasagar", 26.98, 94.63)]
        for v, lat, lon in villages:
            builder = CAPBuilder(sender="test")
            builder.add_info("Flood", "Immediate", "Severe", "Likely", "Head", "Desc", "Inst", [{"areaDesc": v, "circles": [(lat, lon, 5.0)]}])
            xml_str = builder.to_xml_string()
            self.assertIn(v, xml_str)

    def test_short_text_length(self):
        builder = CAPBuilder(sender="test")
        builder.add_info("Flood", "Immediate", "Severe", "Likely", "Head", "A very long description "*10, "A very long instruction "*10, [{"areaDesc": "Village"}])
        short_text = builder.to_short_text()
        self.assertLessEqual(len(short_text.encode("utf-8")), 200)

    def test_short_text_format(self):
        builder = CAPBuilder(sender="test")
        builder.add_info("Flood", "Immediate", "Severe", "Likely", "Head", "Desc", "Inst", [{"areaDesc": "Village"}])
        st = builder.to_short_text()
        self.assertIn("FLOOD ALERT", st)
        self.assertIn("Village", st)
        self.assertIn("IST", st)

    def test_validation_passes(self):
        builder = CAPBuilder(sender="test")
        builder.add_info("Flood", "Immediate", "Severe", "Likely", "Head", "Desc", "Inst", [{"areaDesc": "Village"}])
        self.assertEqual(builder.validate(), [])

    def test_validation_missing_info(self):
        builder = CAPBuilder(sender="test")
        errors = builder.validate()
        self.assertIn("At least one <info> block is required", errors)

    def test_validation_bad_severity(self):
        builder = CAPBuilder(sender="test")
        builder.add_info("Flood", "Immediate", "BadSeverity", "Likely", "Head", "Desc", "Inst", [{"areaDesc": "Village"}])
        errors = builder.validate()
        self.assertTrue(any("Invalid severity" in e for e in errors))

    def test_polygon_closure(self):
        builder = CAPBuilder(sender="test")
        builder.add_info("Flood", "Immediate", "Severe", "Likely", "Head", "Desc", "Inst", [{"areaDesc": "V", "polygons": [[(1,1), (2,2)]]}])
        errors = builder.validate()
        self.assertTrue(any("First and last coordinates must match" in e for e in errors))

    def test_circle_format(self):
        builder = CAPBuilder(sender="test")
        builder.add_info("Flood", "Immediate", "Severe", "Likely", "H", "D", "I", [{"areaDesc": "V", "circles": [(1.23, 4.56, 7.89)]}])
        xml = builder.to_xml_string()
        self.assertIn("<circle>1.23,4.56 7.89</circle>", xml)

    def test_xml_namespace(self):
        builder = CAPBuilder(sender="test")
        builder.add_info("Flood", "Immediate", "Severe", "Likely", "H", "D", "I", [{"areaDesc": "V"}])
        xml = builder.to_xml_string()
        self.assertTrue("xmlns=\"urn:oasis:names:tc:emergency:cap:1.2\"" in xml)

    def test_xml_parseable(self):
        builder = CAPBuilder(sender="test")
        builder.add_info("Flood", "Immediate", "Severe", "Likely", "H", "D", "I", [{"areaDesc": "V"}])
        xml_bytes = builder.to_xml_bytes()
        ET.fromstring(xml_bytes)

    def test_identifier_uniqueness(self):
        b1 = CAPBuilder(sender="t")
        b2 = CAPBuilder(sender="t")
        self.assertNotEqual(b1.identifier, b2.identifier)

    def test_geocode_in_xml(self):
        builder = CAPBuilder(sender="test")
        builder.add_info("Flood", "Immediate", "Severe", "Likely", "H", "D", "I", [{"areaDesc": "V", "geocodes": [("GC", "123")]}])
        xml = builder.to_xml_string()
        self.assertIn("<valueName>GC</valueName>", xml)
        self.assertIn("<value>123</value>", xml)

if __name__ == "__main__":
    unittest.main()

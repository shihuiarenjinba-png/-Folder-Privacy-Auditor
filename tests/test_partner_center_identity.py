from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "store"
IDENTITY_PATH = STORE / "partner-center-identity.json"
SCHEMA_PATH = STORE / "partner-center-identity.schema.json"
BUILDER_PATH = STORE / "build-msix.ps1"
HELPER_PATH = STORE / "identity_manifest.py"

sys.path.insert(0, str(ROOT))
from store.identity_manifest import (  # noqa: E402
    FOUNDATION_NS,
    UAP_NS,
    load_identity,
    release_blockers,
    render_manifest,
    validate_identity_document,
    validate_package_version,
    validate_schema_definition,
)


def synthetic_field(value, status):
    return {
        "value": value,
        "verification_status": status,
        "source_refs": [
            {
                "type": "test_fixture",
                "reference": "Synthetic unit-test data only; not production evidence",
                "path": None,
                "ref": None,
                "commit_sha": None,
                "details": "This value exists only inside a temporary unit-test document.",
            }
        ],
    }


def complete_synthetic_document():
    return {
        "schema_version": 2,
        "product_key": "synthetic-fixture-only",
        "store_id": synthetic_field("A1B2C3D4E5F6", "PARTNER_CENTER_VERIFIED"),
        "display_name": synthetic_field("Synthetic Manifest Fixture", "PARTNER_CENTER_VERIFIED"),
        "identity_name": synthetic_field("OkinawaDesktopTools.SyntheticFixture", "PARTNER_CENTER_VERIFIED"),
        "publisher": synthetic_field("CN=SYNTHETIC-TEST-ONLY", "PARTNER_CENTER_VERIFIED"),
        "publisher_display_name": synthetic_field("SYNTHETIC TEST ONLY", "PARTNER_CENTER_VERIFIED"),
        "package_family_name": synthetic_field(None, "UNKNOWN"),
        "package_sid": synthetic_field(None, "UNKNOWN"),
        "application_version": synthetic_field(None, "UNKNOWN"),
        "package_version": synthetic_field("1.2.3.0", "OWNER_APPROVED"),
    }


class PartnerCenterIdentityTests(unittest.TestCase):
    def test_schema_declares_display_name_and_per_field_status(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(validate_schema_definition(schema), [])
        self.assertEqual(schema["properties"]["schema_version"]["const"], 2)
        self.assertIn("display_name", schema["required"])
        field_schema = schema["properties"]["display_name"]
        self.assertIn("verification_status", field_schema["required"])
        self.assertIn("source_refs", field_schema["required"])
        self.assertIn("SOURCE_FOUND_NOT_LIVE_VERIFIED", field_schema["properties"]["verification_status"]["enum"])

    def test_canonical_json_is_valid_and_has_exact_requested_initial_states(self):
        document = load_identity()
        self.assertEqual(document["schema_version"], 2)
        self.assertEqual(document["product_key"], "folder-privacy-auditor")
        expected = {
            "store_id": "9PKMCT98XQF5",
            "display_name": "Folder Privacy Auditor",
            "identity_name": "OkinawaDesktopTools.FolderPrivacyAuditor",
            "publisher": "CN=46263F21-A700-41DB-8C9B-114C22FB82FC",
            "publisher_display_name": "Okinawa Desktop Tools",
            "package_family_name": "OkinawaDesktopTools.FolderPrivacyAuditor_j8yefg9jgfh58",
            "package_sid": "S-1-15-2-229571055-273319022-1876511600-168570693-2036010400-3661804863-2317016504",
        }
        for name, value in expected.items():
            self.assertEqual(document[name]["value"], value)
            self.assertEqual(document[name]["verification_status"], "PARTNER_CENTER_VERIFIED")
            self.assertTrue(
                any(ref["type"] == "user_provided_partner_center_screenshot"
                    for ref in document[name]["source_refs"]),
                f"{name} must retain Partner Center screenshot provenance",
            )
        self.assertIsNone(document["application_version"]["value"])
        self.assertEqual(document["application_version"]["verification_status"], "UNKNOWN")
        self.assertIsNone(document["package_version"]["value"])
        self.assertEqual(document["package_version"]["verification_status"], "UNKNOWN")
        for name in ("application_version", "package_version"):
            self.assertTrue(document[name]["source_refs"], f"{name} must record what source was inspected")
        self.assertTrue(validate_identity_document(document) == [])

    def test_unresolved_values_block_release_but_not_json_validation(self):
        document = load_identity()
        blockers = release_blockers(document)
        self.assertTrue(blockers)
        self.assertEqual(
            [item for item in blockers if item.startswith(("store_id:", "display_name:", "identity_name:", "publisher:", "publisher_display_name:"))],
            [],
        )
        self.assertTrue(any(item.startswith("package_version:") for item in blockers))

    def test_version_format_keeps_existing_conservative_project_policy(self):
        for version in ("1.0.0.0", "1.2.3.0", "10.65535.65535.0"):
            with self.subTest(version=version):
                validate_package_version(version)
        for version in ("", "1.0.0", "0.1.0.0", "1.0.0.1", "1.65536.0.0", "1.a.0.0"):
            with self.subTest(version=version):
                with self.assertRaises(ValueError):
                    validate_package_version(version)

    def test_synthetic_manifest_mapping_matches_the_document_exactly(self):
        # Synthetic identity values are test-only and never written to the canonical JSON.
        document = complete_synthetic_document()
        self.assertEqual(validate_identity_document(document), [])
        self.assertEqual(release_blockers(document), [])
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "AppxManifest.xml"
            render_manifest(document, output)
            root = ET.parse(output).getroot()
            identity = root.find(f"{{{FOUNDATION_NS}}}Identity")
            props = root.find(f"{{{FOUNDATION_NS}}}Properties")
            visual = root.find(f".//{{{UAP_NS}}}VisualElements")
            self.assertIsNotNone(identity)
            self.assertIsNotNone(props)
            self.assertIsNotNone(visual)
            self.assertEqual(identity.attrib["Name"], document["identity_name"]["value"])
            self.assertEqual(identity.attrib["Publisher"], document["publisher"]["value"])
            self.assertEqual(identity.attrib["Version"], document["package_version"]["value"])
            self.assertEqual(identity.attrib["ProcessorArchitecture"], "x64")
            self.assertEqual(props.find(f"{{{FOUNDATION_NS}}}DisplayName").text, document["display_name"]["value"])
            self.assertEqual(props.find(f"{{{FOUNDATION_NS}}}PublisherDisplayName").text, document["publisher_display_name"]["value"])
            self.assertEqual(visual.attrib["DisplayName"], document["display_name"]["value"])
            self.assertNotIn(document["store_id"]["value"], output.read_text(encoding="utf-8"))

    def test_qa_renderer_uses_explicit_version_without_authorizing_formal_release(self):
        document = complete_synthetic_document()
        document["package_version"] = synthetic_field(None, "UNKNOWN")
        self.assertTrue(release_blockers(document))
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "AppxManifest.xml"
            render_manifest(document, output, qa_version="1.0.77.0")
            root = ET.parse(output).getroot()
            identity = root.find(f"{{{FOUNDATION_NS}}}Identity")
            self.assertEqual(identity.attrib["Version"], "1.0.77.0")
            self.assertIsNone(document["package_version"]["value"])
            self.assertEqual(document["package_version"]["verification_status"], "UNKNOWN")

    def test_renderer_refuses_the_actual_unverified_canonical_document(self):
        document = load_identity()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "must_not_be_created.xml"
            with self.assertRaisesRegex(ValueError, "Formal manifest generation blocked"):
                render_manifest(document, output)
            self.assertFalse(output.exists())

    def test_helper_cli_validates_structure_but_reports_release_hold(self):
        result = subprocess.run(
            [sys.executable, str(HELPER_PATH), "--validate-only"],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("IDENTITY_JSON=VALID", result.stdout)
        self.assertIn("FORMAL_MSIX=BLOCKED", result.stdout)

    def test_helper_cli_release_gate_returns_nonzero_when_unresolved(self):
        result = subprocess.run(
            [sys.executable, str(HELPER_PATH), "--check-release-ready"],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("FORMAL_MSIX=BLOCKED", result.stdout)

    def test_handoff_uses_the_canonical_builder_interface(self):
        handoff = (STORE / "STORE_SUBMISSION_HANDOFF_JA.md").read_text(encoding="utf-8")
        self.assertIn("store/partner-center-identity.json", handoff)
        self.assertIn("store/identity_manifest.py --validate-only", handoff)
        self.assertIn("-ExePath", handoff)
        self.assertIn("-AssetsDirectory", handoff)
        self.assertNotIn("Identity・Publisher・EXE・画像のパスを渡す", handoff)
        self.assertNotIn("-IdentityName", handoff)
        self.assertNotIn("-PublisherDisplayName", handoff)

    def test_builder_uses_canonical_json_not_identity_command_line_overrides(self):
        builder = BUILDER_PATH.read_text(encoding="utf-8")
        parameter_block = builder.split("$ErrorActionPreference", 1)[0]
        self.assertIn("partner-center-identity.json", builder)
        self.assertIn("identity_manifest.py", builder)
        self.assertIn("--check-release-ready", builder)
        self.assertIn("--render-manifest", builder)
        for forbidden in ("[string]$IdentityName", "[string]$Publisher", "[string]$PublisherDisplayName", "[string]$DisplayName", "[string]$Version"):
            self.assertNotIn(forbidden, parameter_block)
        self.assertNotIn("= '1.0.0.0'", builder)
        self.assertNotIn('= "1.0.0.0"', builder)


if __name__ == "__main__":
    unittest.main()

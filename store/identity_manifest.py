"""Validate the canonical Partner Center identity file and render an MSIX manifest.

This module never supplies inferred identity values. The CLI always reads the
single canonical store/partner-center-identity.json file. Tests may pass a
synthetic in-memory record to render_manifest(); that function is not exposed
as a CLI override and test-only records are never written to the product config.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

STORE_DIR = Path(__file__).resolve().parent
IDENTITY_PATH = STORE_DIR / "partner-center-identity.json"
SCHEMA_PATH = STORE_DIR / "partner-center-identity.schema.json"
SCHEMA_VERSION = 2

VERIFICATION_STATUSES = {
    "UNKNOWN",
    "OWNER_PROVIDED_UNVERIFIED",
    "SOURCE_FOUND_NOT_LIVE_VERIFIED",
    "PARTNER_CENTER_VERIFIED",
    "OWNER_APPROVED",
}
FIELD_NAMES = (
    "store_id",
    "display_name",
    "identity_name",
    "publisher",
    "publisher_display_name",
    "package_family_name",
    "package_sid",
    "application_version",
    "package_version",
)
MANIFEST_REQUIRED_FIELDS = (
    "store_id",
    "display_name",
    "identity_name",
    "publisher",
    "publisher_display_name",
)
STORE_ID_RE = re.compile(r"^[A-Z0-9]{12}$")
IDENTITY_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,48}$")
PACKAGE_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+\.0$")

FOUNDATION_NS = "http://schemas.microsoft.com/appx/manifest/foundation/windows10"
UAP_NS = "http://schemas.microsoft.com/appx/manifest/uap/windows10"
UAP10_NS = "http://schemas.microsoft.com/appx/manifest/uap/windows10/10"
RESCAP_NS = "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"


def validate_package_version(value: str) -> None:
    """Raise ValueError unless a version meets the existing project's strict rule.

    This is only a project-level format gate. It does not prove that Partner
    Center will accept a version or that a package has previously been released.
    """
    if not isinstance(value, str) or not PACKAGE_VERSION_RE.fullmatch(value):
        raise ValueError(
            "package_version must be explicitly approved in N.N.N.0 form; "
            "there is no automatic 1.0.0.0 default."
        )
    parts = [int(part) for part in value.split(".")]
    if any(part > 65535 for part in parts):
        raise ValueError("Each package-version component must be <= 65535.")
    if parts[0] < 1:
        raise ValueError("The package-version major component must be >= 1.")
    if parts[3] != 0:
        raise ValueError("The existing project policy requires the fourth component to be 0.")


def validate_identity_document(document: Any) -> list[str]:
    """Return structural/configuration errors without requiring release readiness."""
    errors: list[str] = []
    if not isinstance(document, dict):
        return ["Identity JSON root must be an object."]

    required_top = {"schema_version", "product_key", *FIELD_NAMES}
    missing_top = sorted(required_top - set(document))
    extra_top = sorted(set(document) - required_top)
    if missing_top:
        errors.append("Missing top-level fields: " + ", ".join(missing_top))
    if extra_top:
        errors.append("Unknown top-level fields: " + ", ".join(extra_top))
    if document.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}.")
    product_key = document.get("product_key")
    if not isinstance(product_key, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", product_key):
        errors.append("product_key must be a lowercase hyphen-separated identifier.")

    for name in FIELD_NAMES:
        if name not in document:
            continue
        field = document[name]
        if not isinstance(field, dict):
            errors.append(f"{name} must be an object.")
            continue
        expected_keys = {"value", "verification_status", "source_refs"}
        missing = sorted(expected_keys - set(field))
        extra = sorted(set(field) - expected_keys)
        if missing:
            errors.append(f"{name} is missing: {', '.join(missing)}.")
        if extra:
            errors.append(f"{name} has unknown fields: {', '.join(extra)}.")

        value = field.get("value")
        status = field.get("verification_status")
        if value is not None and (not isinstance(value, str) or not value.strip()):
            errors.append(f"{name}.value must be a non-empty string or null.")
        if status not in VERIFICATION_STATUSES:
            errors.append(f"{name}.verification_status is not an allowed status.")
        elif value is None and status != "UNKNOWN":
            errors.append(f"{name}: a null value must have verification_status UNKNOWN.")
        elif value is not None and status == "UNKNOWN":
            errors.append(f"{name}: a non-null value cannot have verification_status UNKNOWN.")

        refs = field.get("source_refs")
        if not isinstance(refs, list):
            errors.append(f"{name}.source_refs must be an array.")
            continue
        for index, ref in enumerate(refs):
            prefix = f"{name}.source_refs[{index}]"
            if not isinstance(ref, dict):
                errors.append(f"{prefix} must be an object.")
                continue
            required_ref = {"type", "reference", "path", "ref", "commit_sha", "details"}
            missing_ref = sorted(required_ref - set(ref))
            extra_ref = sorted(set(ref) - required_ref)
            if missing_ref:
                errors.append(f"{prefix} is missing: {', '.join(missing_ref)}.")
            if extra_ref:
                errors.append(f"{prefix} has unknown fields: {', '.join(extra_ref)}.")
            for key in ("type", "reference", "details"):
                if key in ref and (not isinstance(ref[key], str) or not ref[key].strip()):
                    errors.append(f"{prefix}.{key} must be a non-empty string.")
            for key in ("path", "ref", "commit_sha"):
                if key in ref and ref[key] is not None and not isinstance(ref[key], str):
                    errors.append(f"{prefix}.{key} must be a string or null.")

    if isinstance(document.get("store_id"), dict):
        store_id = document["store_id"].get("value")
        if store_id is not None and not STORE_ID_RE.fullmatch(store_id):
            errors.append("store_id.value must contain 12 uppercase ASCII letters or digits.")

    if isinstance(document.get("identity_name"), dict):
        identity_name = document["identity_name"].get("value")
        if identity_name is not None and not IDENTITY_NAME_RE.fullmatch(identity_name):
            errors.append("identity_name.value does not meet the conservative package-name syntax check.")

    if isinstance(document.get("publisher"), dict):
        publisher = document["publisher"].get("value")
        if publisher is not None and not publisher.startswith("CN="):
            errors.append("publisher.value must be the exact Publisher distinguished name beginning with CN=.")

    if isinstance(document.get("package_sid"), dict):
        package_sid = document["package_sid"].get("value")
        if package_sid is not None and not re.fullmatch(r"S-1-15-2(?:-\d+)+", package_sid):
            errors.append("package_sid.value does not match the expected package SID notation.")

    if isinstance(document.get("package_version"), dict):
        version_field = document["package_version"]
        version = version_field.get("value")
        status = version_field.get("verification_status")
        if version is not None:
            try:
                validate_package_version(version)
            except ValueError as exc:
                errors.append(f"package_version: {exc}")
            if status != "OWNER_APPROVED":
                errors.append("A non-null package_version must have verification_status OWNER_APPROVED.")

    return errors


def load_identity(path: Path = IDENTITY_PATH) -> dict[str, Any]:
    """Read and structurally validate one identity JSON document."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Canonical identity file is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Canonical identity JSON is invalid: {exc}") from exc
    errors = validate_identity_document(document)
    if errors:
        raise ValueError("Identity JSON validation failed:\n- " + "\n- ".join(errors))
    return document


def release_blockers(document: dict[str, Any]) -> list[str]:
    """List unresolved facts that must block a formal Store MSIX build."""
    structural_errors = validate_identity_document(document)
    if structural_errors:
        return ["Identity JSON invalid: " + error for error in structural_errors]

    blockers: list[str] = []
    for name in MANIFEST_REQUIRED_FIELDS:
        field = document[name]
        if not field["value"]:
            blockers.append(f"{name}: value is null or empty.")
            continue
        if field["verification_status"] != "PARTNER_CENTER_VERIFIED":
            blockers.append(
                f"{name}: verification_status is {field['verification_status']}; "
                "PARTNER_CENTER_VERIFIED is required."
            )

    version = document["package_version"]
    if not version["value"]:
        blockers.append("package_version: no explicitly approved package version is recorded.")
    elif version["verification_status"] != "OWNER_APPROVED":
        blockers.append(
            f"package_version: status is {version['verification_status']}; OWNER_APPROVED is required."
        )
    else:
        try:
            validate_package_version(version["value"])
        except ValueError as exc:
            blockers.append(f"package_version: {exc}")

    return blockers


def _q(namespace: str, local_name: str) -> str:
    return f"{{{namespace}}}{local_name}"


def verify_manifest_identity(manifest_path: Path, document: dict[str, Any]) -> None:
    """Raise ValueError if the generated manifest doesn't exactly match the source."""
    try:
        root = ET.parse(manifest_path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise ValueError(f"Generated AppxManifest.xml cannot be parsed: {exc}") from exc

    identity = root.find(_q(FOUNDATION_NS, "Identity"))
    properties = root.find(_q(FOUNDATION_NS, "Properties"))
    if identity is None or properties is None:
        raise ValueError("Generated manifest is missing Identity or Properties.")
    expected_identity = {
        "Name": document["identity_name"]["value"],
        "Publisher": document["publisher"]["value"],
        "Version": document["package_version"]["value"],
        "ProcessorArchitecture": "x64",
    }
    for key, expected in expected_identity.items():
        if identity.attrib.get(key) != expected:
            raise ValueError(f"Generated manifest Identity.{key} doesn't match the canonical JSON.")

    expected_properties = {
        "DisplayName": document["display_name"]["value"],
        "PublisherDisplayName": document["publisher_display_name"]["value"],
    }
    for key, expected in expected_properties.items():
        node = properties.find(_q(FOUNDATION_NS, key))
        if node is None or node.text != expected:
            raise ValueError(f"Generated manifest Properties/{key} doesn't match the canonical JSON.")

    visual = root.find(f".//{_q(UAP_NS, 'VisualElements')}")
    if visual is None or visual.attrib.get("DisplayName") != document["display_name"]["value"]:
        raise ValueError("Generated manifest VisualElements.DisplayName doesn't match the canonical JSON.")


def render_manifest(document: dict[str, Any], output_path: Path) -> None:
    """Render an AppxManifest.xml from a complete, verified configuration.

    Production CLI calls this only with the canonical JSON. It intentionally
    refuses all unverified values and refuses to overwrite an existing file.
    """
    blockers = release_blockers(document)
    if blockers:
        raise ValueError("Formal manifest generation blocked:\n- " + "\n- ".join(blockers))
    output_path = Path(output_path)
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing manifest: {output_path}")
    if not output_path.parent.is_dir():
        raise FileNotFoundError(f"Manifest output directory doesn't exist: {output_path.parent}")

    ET.register_namespace("", FOUNDATION_NS)
    ET.register_namespace("uap", UAP_NS)
    ET.register_namespace("uap10", UAP10_NS)
    ET.register_namespace("rescap", RESCAP_NS)

    root = ET.Element(
        _q(FOUNDATION_NS, "Package"),
        {"IgnorableNamespaces": "uap uap10 rescap"},
    )
    ET.SubElement(
        root,
        _q(FOUNDATION_NS, "Identity"),
        {
            "Name": document["identity_name"]["value"],
            "Publisher": document["publisher"]["value"],
            "Version": document["package_version"]["value"],
            "ProcessorArchitecture": "x64",
        },
    )
    properties = ET.SubElement(root, _q(FOUNDATION_NS, "Properties"))
    ET.SubElement(properties, _q(FOUNDATION_NS, "DisplayName")).text = document["display_name"]["value"]
    ET.SubElement(properties, _q(FOUNDATION_NS, "PublisherDisplayName")).text = document["publisher_display_name"]["value"]
    ET.SubElement(properties, _q(FOUNDATION_NS, "Description")).text = "Local read-only folder privacy audit"
    ET.SubElement(properties, _q(FOUNDATION_NS, "Logo")).text = r"Assets\StoreLogo.png"

    resources = ET.SubElement(root, _q(FOUNDATION_NS, "Resources"))
    ET.SubElement(resources, _q(FOUNDATION_NS, "Resource"), {"Language": "ja-JP"})
    ET.SubElement(resources, _q(FOUNDATION_NS, "Resource"), {"Language": "en-US"})

    dependencies = ET.SubElement(root, _q(FOUNDATION_NS, "Dependencies"))
    ET.SubElement(
        dependencies,
        _q(FOUNDATION_NS, "TargetDeviceFamily"),
        {
            "Name": "Windows.Desktop",
            "MinVersion": "10.0.19041.0",
            "MaxVersionTested": "10.0.26100.0",
        },
    )

    applications = ET.SubElement(root, _q(FOUNDATION_NS, "Applications"))
    application = ET.SubElement(
        applications,
        _q(FOUNDATION_NS, "Application"),
        {
            "Id": "App",
            "Executable": "FolderPrivacyAuditor.exe",
            _q(UAP10_NS, "RuntimeBehavior"): "packagedClassicApp",
            _q(UAP10_NS, "TrustLevel"): "mediumIL",
        },
    )
    ET.SubElement(
        application,
        _q(UAP_NS, "VisualElements"),
        {
            "DisplayName": document["display_name"]["value"],
            "Description": "Local read-only folder privacy audit",
            "BackgroundColor": "transparent",
            "Square150x150Logo": r"Assets\Square150x150Logo.png",
            "Square44x44Logo": r"Assets\Square44x44Logo.png",
        },
    )
    capabilities = ET.SubElement(root, _q(FOUNDATION_NS, "Capabilities"))
    ET.SubElement(capabilities, _q(RESCAP_NS, "Capability"), {"Name": "runFullTrust"})

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    output_path.write_bytes(
        ET.tostring(root, encoding="utf-8", xml_declaration=True)
    )
    verify_manifest_identity(output_path, document)


def _read_canonical() -> dict[str, Any]:
    return load_identity(IDENTITY_PATH)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--validate-only", action="store_true", help="Validate JSON/schema structure without requiring release readiness.")
    group.add_argument("--check-release-ready", action="store_true", help="Return nonzero unless all release-required values are verified.")
    group.add_argument("--render-manifest", metavar="PATH", help="Render a production manifest only when the canonical config is release-ready.")
    args = parser.parse_args(argv)

    try:
        document = _read_canonical()
        if args.validate_only:
            print(f"IDENTITY_JSON=VALID schema_version={SCHEMA_VERSION}")
            blockers = release_blockers(document)
            if blockers:
                print("FORMAL_MSIX=BLOCKED")
                for blocker in blockers:
                    print(f"BLOCKER: {blocker}")
            else:
                print("FORMAL_MSIX=READY_FOR_BUILD_GATE")
            return 0

        if args.check_release_ready:
            blockers = release_blockers(document)
            if blockers:
                print("FORMAL_MSIX=BLOCKED")
                for blocker in blockers:
                    print(f"BLOCKER: {blocker}")
                return 2
            print("FORMAL_MSIX=READY_FOR_BUILD_GATE")
            return 0

        if args.render_manifest:
            output_path = Path(args.render_manifest)
            render_manifest(document, output_path)
            print(f"MANIFEST_CREATED={output_path}")
            print("MANIFEST_IDENTITY_MATCH=PASS")
            return 0
    except (ValueError, OSError) as exc:
        print(f"IDENTITY_ERROR: {exc}", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

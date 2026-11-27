"""Deterministic registration-specific account-opening requirements."""
from __future__ import annotations

from typing import Any


REGISTRATION_REQUIREMENTS: dict[str, tuple[dict[str, Any], ...]] = {
    "INDIVIDUAL": (
        {"key": "PRIMARY_OWNER_DETAILS", "label": "Primary owner details", "rule": "MANDATORY"},
        {"key": "JOINT_OWNER_DETAILS", "label": "Joint owner details", "rule": "JOINT_ONLY"},
        {"key": "BENEFICIARY_DETAILS", "label": "Beneficiary details", "rule": "OPTIONAL"},
        {"key": "CLIENT_PROFILE_CONFIRMATION", "label": "Client profile confirmation", "rule": "MANDATORY"},
        {"key": "RISK_ASSESSMENT", "label": "Risk assessment", "rule": "MANDATORY"},
    ),
    "INDIVIDUAL_TOD": (
        {"key": "PRIMARY_OWNER_DETAILS", "label": "Primary owner details", "rule": "MANDATORY"},
        {"key": "JOINT_OWNER_DETAILS", "label": "Joint owner details", "rule": "JOINT_ONLY"},
        {"key": "BENEFICIARY_DETAILS", "label": "Beneficiary details", "rule": "OPTIONAL"},
        {"key": "CLIENT_PROFILE_CONFIRMATION", "label": "Client profile confirmation", "rule": "MANDATORY"},
        {"key": "RISK_ASSESSMENT", "label": "Risk assessment", "rule": "MANDATORY"},
    ),
    "JOINT": (
        {"key": "PRIMARY_OWNER_DETAILS", "label": "Primary owner details", "rule": "MANDATORY"},
        {"key": "JOINT_OWNER_DETAILS", "label": "Joint owner details", "rule": "JOINT_ONLY"},
        {"key": "BENEFICIARY_DETAILS", "label": "Beneficiary details", "rule": "OPTIONAL"},
        {"key": "CLIENT_PROFILE_CONFIRMATION", "label": "Client profile confirmation", "rule": "MANDATORY"},
        {"key": "RISK_ASSESSMENT", "label": "Risk assessment", "rule": "MANDATORY"},
    ),
    "JOINT_TOD": (
        {"key": "PRIMARY_OWNER_DETAILS", "label": "Primary owner details", "rule": "MANDATORY"},
        {"key": "JOINT_OWNER_DETAILS", "label": "Joint owner details", "rule": "JOINT_ONLY"},
        {"key": "BENEFICIARY_DETAILS", "label": "Beneficiary details", "rule": "OPTIONAL"},
        {"key": "CLIENT_PROFILE_CONFIRMATION", "label": "Client profile confirmation", "rule": "MANDATORY"},
        {"key": "RISK_ASSESSMENT", "label": "Risk assessment", "rule": "MANDATORY"},
    ),
}


def build_registration_requirements(registration_type: str) -> dict[str, Any]:
    """Return the resolved requirements for one supported registration type."""
    normalized = str(registration_type or "").strip().upper()
    if normalized not in REGISTRATION_REQUIREMENTS:
        raise ValueError(f"Unsupported registration type: {registration_type!r}")

    resolved: list[dict[str, Any]] = []
    for definition in REGISTRATION_REQUIREMENTS[normalized]:
        rule = definition["rule"]
        if rule == "MANDATORY":
            status, required = "MANDATORY", True
        elif rule == "OPTIONAL":
            status, required = "OPTIONAL", False
        elif rule == "JOINT_ONLY" and normalized in {"JOINT", "JOINT_TOD"}:
            status, required = "MANDATORY", True
        else:
            status, required = "NOT_REQUIRED", False
        resolved.append({
            "key": definition["key"],
            "label": definition["label"],
            "status": status,
            "required": required,
        })

    return {"registrationType": normalized, "requirements": resolved}

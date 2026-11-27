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


PRODUCT_FEATURES: dict[str, tuple[dict[str, Any], ...]] = {
    "BROKERAGE": (
        {"name": "cashSweepVehicle", "label": "Sweep vehicle", "type": "select", "required": False, "options": ["BDP"], "defaultValue": "BDP"},
        {"name": "linkedBankingAccount", "label": "Link existing banking account", "type": "text", "required": False, "placeholder": "Select or enter an existing banking account"},
        {"name": "optionsTradingElection", "label": "Opt in to Options?", "type": "select", "required": False, "options": ["YES", "NO"], "defaultValue": "NO"},
        {"name": "mutualFundsTaxLotMethod", "label": "Mutual Funds", "type": "select", "required": False, "options": ["FIRST_IN_FIRST_OUT", "LAST_IN_FIRST_OUT"], "defaultValue": "FIRST_IN_FIRST_OUT"},
        {"name": "otherSecuritiesTaxLotMethod", "label": "All Other Securities", "type": "select", "required": False, "options": ["FIRST_IN_FIRST_OUT", "LAST_IN_FIRST_OUT"], "defaultValue": "FIRST_IN_FIRST_OUT"},
    ),
    "CREDIT_FACILITY": (
        {"name": "requestedCreditLimit", "label": "Requested credit limit (account currency)", "type": "number", "required": True, "placeholder": "Enter amount in the account currency"},
        {"name": "collateralType", "label": "Proposed collateral", "type": "select", "required": True, "options": ["SECURITIES", "CASH", "OTHER"]},
        {"name": "facilityPurpose", "label": "Facility purpose", "type": "select", "required": True, "options": ["LIQUIDITY", "INVESTMENT", "OTHER"]},
    ),
}


def build_product_feature_requirements(product_type: str) -> dict[str, Any]:
    """Return the POC feature-capture schema for the selected product."""
    normalized = str(product_type or "").strip().upper()
    if normalized not in PRODUCT_FEATURES:
        raise ValueError(f"Unsupported product type: {product_type!r}")
    return {
        "productType": normalized,
        "fields": [dict(field) for field in PRODUCT_FEATURES[normalized]],
    }

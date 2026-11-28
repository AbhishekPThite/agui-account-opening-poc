"""Deterministic domain assessment of account-opening completeness.

This module has no LangGraph or presentation dependencies. It evaluates the
current workflow data and returns section-level status and missing fields.
"""
from __future__ import annotations

from typing import Any

from .requirements import build_product_feature_requirements


SUPPORTED_PRODUCTS = {"BROKERAGE", "CREDIT_FACILITY"}
SUPPORTED_REGISTRATIONS = {"INDIVIDUAL", "INDIVIDUAL_TOD", "JOINT", "JOINT_TOD"}
JOINT_REGISTRATIONS = {"JOINT", "JOINT_TOD"}
RISK_FIELDS = (
    "investmentObjectives",
    "investmentTimeHorizon",
    "liquidityNeeds",
    "riskTolerance",
)


def assess_application(state: dict[str, Any]) -> dict[str, Any]:
    """Return authoritative section statuses and missing fields for this POC."""
    ownership = str(state.get("ownership", "INDIVIDUAL")).upper()
    product_type = str(state.get("product_type") or state.get("account_type") or "").upper()

    account_missing: list[str] = []
    if product_type not in SUPPORTED_PRODUCTS:
        account_missing.append("productType")
    if ownership not in SUPPORTED_REGISTRATIONS:
        account_missing.append("registrationType")
    if not str(state.get("account_nickname") or "Brokerage 1").strip():
        account_missing.append("accountNickname")
    if ownership in JOINT_REGISTRATIONS:
        if not str(state.get("joint_owner_name", "")).strip():
            account_missing.append("jointOwnerName")
        if not str(state.get("joint_owner_tax_residency", "")).strip():
            account_missing.append("jointOwnerTaxResidency")

    profile_assessment = state.get("profile_assessment", {})
    profile_missing_fields = list(profile_assessment.get("actionRequired", []))
    for group in profile_assessment.get("sections", []):
        for field in group.get("fields", []):
            if field.get("missing"):
                missing_identifier = field.get("name") or field.get("label")
                if missing_identifier and missing_identifier not in profile_missing_fields:
                    profile_missing_fields.append(missing_identifier)
    profile_missing = bool(profile_missing_fields)
    profile_status = (
        "ACTION_REQUIRED" if profile_missing else
        "COMPLETED" if profile_assessment else
        "PENDING"
    )

    risk = state.get("risk_assessment", {})
    risk_missing = [
        key for key in RISK_FIELDS
        if risk.get(key) is None or risk.get(key) == "" or risk.get(key) == []
    ]

    feature_schema = (
        build_product_feature_requirements(product_type)
        if product_type in SUPPORTED_PRODUCTS else {"fields": []}
    )
    features = state.get("product_features", {})
    feature_missing = [
        field["name"]
        for field in feature_schema["fields"]
        if field.get("required")
        and features.get(field["name"]) in (None, "")
        and field.get("defaultValue") in (None, "")
    ]

    statuses = {
        "ACCOUNT_DETAILS": "ACTION_REQUIRED" if account_missing else "COMPLETED",
        "PROFILE": profile_status,
        "RISK_PROFILE": "ACTION_REQUIRED" if risk_missing else "COMPLETED",
        "FEATURES": (
            "PENDING" if not product_type else
            "ACTION_REQUIRED" if feature_missing else
            "COMPLETED"
        ),
    }
    draft_created = bool(state.get("application"))
    statuses["SUMMARY"] = (
        "COMPLETED" if draft_created else
        "ACTION_REQUIRED"
        if all(statuses[key] == "COMPLETED" for key in ("PROFILE", "ACCOUNT_DETAILS", "RISK_PROFILE", "FEATURES"))
        else "PENDING"
    )

    return {
        "statuses": statuses,
        "missing_fields": {
            "ACCOUNT_DETAILS": account_missing,
            "PROFILE": profile_missing_fields,
            "RISK_PROFILE": risk_missing,
            "FEATURES": feature_missing,
        },
        "draft_created": draft_created,
    }

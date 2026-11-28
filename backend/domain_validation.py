"""Deterministic domain validation for account-opening request data.

LLM extraction and UI parsing provide candidate values. This module validates
those candidates against workflow/domain rules before graph state is updated.
"""
from __future__ import annotations

from typing import Any

from requirements_engine import build_product_feature_requirements


RISK_FIELDS = (
    "investmentObjectives",
    "investmentTimeHorizon",
    "liquidityNeeds",
    "riskTolerance",
)

ALLOWED_RISK_VALUES = {
    "riskTolerance": {"CONSERVATIVE", "MODERATE", "AGGRESSIVE"},
    "investmentTimeHorizon": {"UNDER_3_YEARS", "3_TO_5_YEARS", "5_TO_10_YEARS", "OVER_10_YEARS"},
    "liquidityNeeds": {"LOW", "MEDIUM", "HIGH"},
}

SUPPORTED_PRODUCTS = {"BROKERAGE", "CREDIT_FACILITY"}


def validate_joint_owner_submission(extracted: dict[str, Any]) -> None:
    """Reject a submitted joint-owner form if either required field is absent."""
    required_fields = ("jointOwnerName", "jointOwnerTaxResidency")
    missing = [
        key for key in required_fields
        if not str(extracted.get(key, "")).strip()
    ]
    if missing:
        raise ValueError("Joint-owner details are incomplete. Required fields: " + ", ".join(missing))


def validate_risk_assessment(
    extracted: dict[str, Any],
    *,
    requested: bool,
    submission: bool,
) -> dict[str, Any]:
    """Normalize explicit risk answers; enforce completeness only on submission."""
    if not requested:
        return {}

    submitted = {
        key: str(extracted.get(key, "")).strip()
        for key in RISK_FIELDS
        if str(extracted.get(key, "")).strip()
    }

    if not submission:
        return submitted

    missing = [key for key in RISK_FIELDS if not submitted.get(key)]
    if missing:
        raise ValueError("Risk assessment is incomplete. Required fields: " + ", ".join(missing))

    submitted["investmentObjectives"] = [
        value.strip().upper()
        for value in submitted["investmentObjectives"].split(",")
        if value.strip()
    ]
    submitted["riskTolerance"] = submitted["riskTolerance"].upper()
    submitted["investmentTimeHorizon"] = submitted["investmentTimeHorizon"].upper()
    submitted["liquidityNeeds"] = submitted["liquidityNeeds"].upper()

    invalid = [
        key for key, allowed in ALLOWED_RISK_VALUES.items()
        if submitted[key] not in allowed
    ]
    if not submitted["investmentObjectives"] or invalid:
        raise ValueError(
            "Risk assessment contains invalid values: "
            + ", ".join(invalid or ["investmentObjectives"])
        )
    return submitted


def validate_product_features(
    extracted: dict[str, Any],
    *,
    product_type: str,
    requested: bool,
    submission: bool,
) -> dict[str, Any]:
    """Validate product-specific values; enforce required fields on submission."""
    if not requested:
        return {}
    if product_type not in SUPPORTED_PRODUCTS:
        raise ValueError("Select a supported product type before capturing product features.")

    feature_fields = build_product_feature_requirements(product_type)["fields"]
    submitted: dict[str, Any] = {}

    for field in feature_fields:
        name = field["name"]
        value = str(extracted.get(name, "")).strip()
        if not value:
            if submission and field.get("required"):
                raise ValueError("Product features are incomplete. Required fields: " + name)
            continue

        if field["type"] == "select":
            value = value.upper()
            if value not in field["options"]:
                if submission:
                    raise ValueError(f"Unsupported value for {name}: {value}")
                # Conversational prefill is best-effort: ignore unsupported
                # candidates and preserve the previously accepted state value.
                continue
        elif field["type"] == "number":
            try:
                value = float(value.replace(",", ""))
            except ValueError as exc:
                raise ValueError(f"{name} must be a valid number.") from exc
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero.")

        submitted[name] = value

    return submitted

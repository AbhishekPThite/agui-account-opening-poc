"""Presentation projections for account-opening UI payloads.

These functions translate domain assessment and workflow state into stable
UI-facing data structures. They do not execute graph nodes or route workflow.
"""
from __future__ import annotations

from typing import Any

from application_assessment import assess_application
from requirements_engine import build_product_feature_requirements
from workflow_state import AccountOpeningState


def build_journey_status(state: AccountOpeningState) -> dict[str, Any]:
    """Project domain assessment into the dashboard's journey-status UI contract."""
    assessment = assess_application(state)
    widget_id = state.get("ui", {}).get("widgetId", "")
    current_by_widget = {
        "APPLICATION_DASHBOARD": "DASHBOARD",
        "PROFILE_ASSESSMENT": "PROFILE",
        "PROFILE_DATA_CAPTURE": "PROFILE",
        "ACCOUNT_SETUP_FORM": "ACCOUNT_DETAILS",
        "JOINT_OWNER_FORM": "ACCOUNT_DETAILS",
        "BENEFICIARY_CAPTURE": "ACCOUNT_DETAILS",
        "RISK_ASSESSMENT_FORM": "RISK_PROFILE",
        "PRODUCT_FEATURES_FORM": "FEATURES",
        "APPLICATION_SUMMARY": "SUMMARY",
        "DRAFT_CONFIRMATION": "SUMMARY",
    }

    stage_definitions = [
        ("ACCOUNT_DETAILS", "Account Details", "Select product, registration and account ownership details."),
        ("PROFILE", "Client Profile", "Review existing client information and complete missing mandatory details."),
        ("RISK_PROFILE", "Risk Profile", "Review objectives, time horizon, liquidity and risk tolerance."),
        ("FEATURES", "Features", "Review product-specific elections and preferences."),
        ("SUMMARY", "Summary", "Review the complete application before explicit draft approval."),
    ]
    stages = [
        {"id": section_id, "label": label, "status": assessment["statuses"][section_id]}
        for section_id, label, _ in stage_definitions
    ]
    completed_count = sum(1 for stage in stages if stage["status"] == "COMPLETED")
    return {
        "stages": stages,
        "currentStage": current_by_widget.get(widget_id),
        "completedCount": completed_count,
        "totalCount": len(stages),
        "overallStatus": "COMPLETED" if completed_count == len(stages) else "IN_PROGRESS",
        "sections": [
            {
                "id": section_id,
                "label": label,
                "status": assessment["statuses"][section_id],
                "description": description,
            }
            for section_id, label, description in stage_definitions
        ],
    }


def build_application_review_sections(state: AccountOpeningState) -> list[dict[str, Any]]:
    """Project the authoritative domain assessment into read-only review sections."""
    profile = state.get("client_profile", {})
    profile_assessment = state.get("profile_assessment", {})
    ownership = str(state.get("ownership", "INDIVIDUAL")).upper()
    product_type = str(state.get("product_type") or state.get("account_type") or "").upper()
    risk = state.get("risk_assessment", {})
    features = state.get("product_features", {})
    domain_assessment = assess_application(state)
    missing_by_section = domain_assessment["missing_fields"]
    sections: list[dict[str, Any]] = []

    def field(
        label: str,
        value: Any,
        required: bool = False,
        domain_key: str | None = None,
        section_id: str | None = None,
    ) -> dict[str, Any]:
        present = value is not None and value != "" and value != []
        if isinstance(value, list):
            display = ", ".join(str(item) for item in value) if value else "Not provided"
        else:
            display = str(value) if present else "Not provided"
        missing = (
            domain_key in missing_by_section.get(section_id, [])
            if required and domain_key and section_id
            else required and not present
        )
        return {
            "label": label,
            "value": display,
            "required": required,
            "missing": missing,
        }

    account_fields = [
        field("Product type", product_type, True, "productType", "ACCOUNT_DETAILS"),
        field("Registration type", ownership, True, "registrationType", "ACCOUNT_DETAILS"),
        field("Account nickname", state.get("account_nickname") or "Brokerage 1", True,
              "accountNickname", "ACCOUNT_DETAILS"),
        field("Margin option", state.get("margin_option", "NONE")),
    ]
    if ownership in {"JOINT", "JOINT_TOD"}:
        account_fields.extend([
            field("Joint owner full name", state.get("joint_owner_name"), True,
                  "jointOwnerName", "ACCOUNT_DETAILS"),
            field("Joint owner tax residency", state.get("joint_owner_tax_residency"), True,
                  "jointOwnerTaxResidency", "ACCOUNT_DETAILS"),
        ])
    beneficiary = state.get("beneficiary_data", {})
    account_fields.extend([
        field("Beneficiary full name", beneficiary.get("beneficiaryFullName")),
        field("Beneficiary relationship", beneficiary.get("beneficiaryRelationship")),
        field("Beneficiary date of birth", beneficiary.get("beneficiaryDateOfBirth")),
    ])
    sections.append({
        "id": "ACCOUNT_DETAILS",
        "label": "Account Details",
        "status": domain_assessment["statuses"]["ACCOUNT_DETAILS"],
        "fields": account_fields,
    })

    profile_fields: list[dict[str, Any]] = [
        field("Client name", profile.get("displayName")),
        field("Client ID", profile.get("clientId") or state.get("client_id"), True),
        field("KYC status", profile.get("kycStatus")),
    ]
    for group in profile_assessment.get("sections", []):
        for item in group.get("fields", []):
            profile_fields.append({
                "label": f"{group.get('name', 'Profile')} · {item.get('label', '')}",
                "value": item.get("value", "Not provided"),
                "required": bool(item.get("required")),
                "missing": bool(item.get("missing")),
            })
    sections.append({
        "id": "PROFILE",
        "label": "Client Profile",
        "status": domain_assessment["statuses"]["PROFILE"],
        "fields": profile_fields,
    })

    risk_fields = [
        field("Investment objectives", risk.get("investmentObjectives"), True,
              "investmentObjectives", "RISK_PROFILE"),
        field("Investment time horizon", risk.get("investmentTimeHorizon"), True,
              "investmentTimeHorizon", "RISK_PROFILE"),
        field("Liquidity needs", risk.get("liquidityNeeds"), True,
              "liquidityNeeds", "RISK_PROFILE"),
        field("Risk tolerance", risk.get("riskTolerance"), True,
              "riskTolerance", "RISK_PROFILE"),
    ]
    sections.append({
        "id": "RISK_PROFILE",
        "label": "Risk Assessment",
        "status": domain_assessment["statuses"]["RISK_PROFILE"],
        "fields": risk_fields,
    })

    feature_schema = (
        build_product_feature_requirements(product_type)
        if product_type in {"BROKERAGE", "CREDIT_FACILITY"}
        else {"fields": []}
    )
    feature_fields = [
        field(
            definition["label"],
            (
                features.get(definition["name"])
                if features.get(definition["name"]) not in (None, "")
                else definition.get("defaultValue")
            ),
            bool(definition.get("required")),
            definition["name"],
            "FEATURES",
        )
        for definition in feature_schema["fields"]
    ]
    sections.append({
        "id": "FEATURES",
        "label": "Product Features",
        "status": domain_assessment["statuses"]["FEATURES"],
        "fields": feature_fields,
    })
    return sections

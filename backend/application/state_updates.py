"""Pure projection of validated request data into LangGraph state updates."""
from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from .workflow_actions import WorkflowActionContext
from ..workflow.state import AccountOpeningState


def _extract_value(pattern: str, text: str, default: str = "") -> str:
    import re
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else default


def build_state_updates(
    state: AccountOpeningState,
    *,
    extracted: dict[str, Any],
    text: str,
    actions: WorkflowActionContext,
    form_submission: bool,
    assistant_answer: str,
    submitted_risk: dict[str, Any],
    submitted_features: dict[str, Any],
) -> dict[str, Any]:
    """Build a partial state update without mutating the input state."""
    client_id = extracted.get("client_id") or extracted.get("clientId") or _extract_value(
        r"\bclient\s+([A-Z0-9-]+)", text, state.get("client_id", "C12345")
    )

    allowed_products = {"BROKERAGE", "CREDIT_FACILITY"}
    allowed_registrations = {"INDIVIDUAL", "INDIVIDUAL_TOD", "JOINT", "JOINT_TOD"}
    raw_product = str(
        extracted.get("productType") or extracted.get("account_type") or ""
    ).strip().upper()
    raw_registration = str(
        extracted.get("registrationType") or extracted.get("ownership") or ""
    ).strip().upper()

    product_type = raw_product if raw_product in allowed_products else state.get("product_type", "")
    ownership = (
        raw_registration if raw_registration in allowed_registrations
        else state.get("ownership", "INDIVIDUAL")
    )
    owner = extracted.get("joint_owner_name") or _extract_value(
        r"(?:joint owner|co-owner)(?: name)?\s*(?:is|:|to)\s*([A-Za-z][A-Za-z .'-]+?)(?:,|;|$)",
        text, state.get("joint_owner_name", "")
    )
    tax = extracted.get("joint_owner_tax_residency") or _extract_value(
        r"(?:tax residency|residency)\s*(?:is|:|to)\s*([A-Za-z][A-Za-z .'-]+?)(?:,|;|$)",
        text, state.get("joint_owner_tax_residency", "")
    )

    beneficiary_values = {
        key: str(extracted.get(key, "")).strip()
        for key in ("beneficiaryFullName", "beneficiaryRelationship", "beneficiaryDateOfBirth")
        if str(extracted.get(key, "")).strip()
    } if (actions.beneficiary_capture or actions.beneficiary_prefill) else {}
    captured_values = {
        str(key): value for key, value in extracted.items()
        if key not in {"formId", "clientId"} and value is not None and str(value).strip() != ""
    } if (actions.profile_capture or actions.profile_data_prefill) else {}
    explicitly_confirmed_values = {
        item["field"]: item["value"]
        for item in state.get("profile_assessment", {}).get("confirmationRequired", [])
        if item.get("field")
    } if actions.profile_confirmed else {}
    profile_values_to_merge = {**explicitly_confirmed_values, **captured_values}
    selected_product = str(extracted.get("productType") or product_type).upper()
    selected_registration = str(extracted.get("registrationType") or ownership).upper()

    return {
        "client_id": str(extracted.get("clientId") or client_id),
        "account_type": selected_product,
        "product_type": selected_product,
        "ownership": selected_registration,
        "account_nickname": str(
            extracted.get("account_nickname")
            or extracted.get("accountNickname")
            or state.get("account_nickname")
            or "Brokerage 1"
        ),
        "margin_option": (
            str(extracted.get("margin_option") or extracted.get("marginOption")).upper()
            if str(extracted.get("margin_option") or extracted.get("marginOption") or "").upper() in {"NONE", "MARGIN"}
            else state.get("margin_option", "NONE")
        ),
        "account_setup_complete": actions.setup_submitted or state.get("account_setup_complete", False),
        "profile_confirmed": actions.profile_confirmed or state.get("profile_confirmed", False),
        "profile_capture_requested": actions.profile_capture_requested,
        "profile_data_submitted": actions.profile_capture or state.get("profile_data_submitted", False),
        "confirmed_profile_data": {
            **state.get("confirmed_profile_data", {}),
            **profile_values_to_merge,
        },
        "application_data": {
            **state.get("application_data", {}),
            **profile_values_to_merge,
        },
        "beneficiary_data": {
            **state.get("beneficiary_data", {}),
            **beneficiary_values,
        },
        "beneficiary_capture_completed": (
            actions.beneficiary_capture or actions.beneficiary_skip
            or state.get("beneficiary_capture_completed", False)
        ),
        "risk_assessment": {**state.get("risk_assessment", {}), **submitted_risk},
        "risk_assessment_completed": (
            actions.risk_assessment_submission or state.get("risk_assessment_completed", False)
        ),
        "product_features": {**state.get("product_features", {}), **submitted_features},
        "product_features_completed": (
            actions.product_features_submission or state.get("product_features_completed", False)
        ),
        "joint_owner_name": str(
            extracted.get("jointOwnerName") or owner or state.get("joint_owner_name", "")
        ),
        "joint_owner_tax_residency": str(
            extracted.get("jointOwnerTaxResidency") or tax
            or state.get("joint_owner_tax_residency", "")
        ),
        "messages": [AIMessage(content=assistant_answer)] if assistant_answer else [],
        "conversation_only": bool(assistant_answer),
        "dashboard_navigation": actions.dashboard_navigation,
        "requested_section": actions.requested_section,
        "last_form_action": str(extracted.get("formId", "")) if form_submission else "",
    }

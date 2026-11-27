from __future__ import annotations

import json
import re
import uuid
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from checkpointer import checkpointer
from langgraph.types import interrupt
from model_client import (
    extract_account_request,
    extract_risk_assessment,
    extract_product_features,
    extract_active_form_fields,
    answer_journey_question,
    model,
)
from requirements_engine import build_registration_requirements, build_product_feature_requirements


class AccountOpeningState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    client_id: str
    account_type: str
    ownership: str
    joint_owner_name: str
    joint_owner_tax_residency: str
    client_profile: dict[str, Any]
    ui: dict[str, Any]
    application: dict[str, Any]
    missing_fields: list[str]
    approval_status: str
    review_action: str
    review_revision: int
    draft_idempotency_key: str
    product_type: str
    account_nickname: str
    margin_option: str
    account_setup_complete: bool
    profile_confirmed: bool
    profile_capture_requested: bool
    profile_data_submitted: bool
    profile_assessment: dict[str, Any]
    confirmed_profile_data: dict[str, Any]
    application_data: dict[str, Any]
    requirements_assessment: dict[str, Any]
    beneficiary_data: dict[str, Any]
    beneficiary_capture_completed: bool
    risk_assessment: dict[str, Any]
    risk_assessment_completed: bool
    product_features: dict[str, Any]
    product_features_completed: bool
    journey_status: dict[str, Any]
    conversation_only: bool
    dashboard_navigation: bool
    requested_section: str
    last_form_action: str


EDITABLE_FIELDS = {
    "client_id": "client_id",
    "account_type": "account_type",
    "ownership": "ownership",
    "joint_owner_name": "joint_owner_name",
    "joint_owner_tax_residency": "joint_owner_tax_residency",
}


def latest_user_text(messages: list[AnyMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            content = message.content
            return content if isinstance(content, str) else str(content)
    return ""


def extract_value(pattern: str, text: str, default: str = "") -> str:
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else default


async def understand_request(state: AccountOpeningState) -> dict[str, Any]:
    text = latest_user_text(state.get("messages", []))
    extracted: dict[str, Any] = {}
    form_submission = text.startswith("POC_FORM_SUBMISSION:")
    if form_submission:
        try:
            extracted = json.loads(text.split(":", 1)[1])
        except (json.JSONDecodeError, IndexError):
            raise ValueError("The submitted account setup form could not be read.")
    active_widget = state.get("ui", {}).get("widgetId", "")
    active_ui = state.get("ui", {})
    assistant_answer = ""
    if not form_submission and text:
        if active_widget == "RISK_ASSESSMENT_FORM":
            extracted = await extract_risk_assessment(text) if model is not None else {}
        elif active_widget == "PRODUCT_FEATURES_FORM":
            active_product = str(state.get("product_type", state.get("account_type", ""))).upper()
            product_schema = build_product_feature_requirements(active_product)
            extracted = await extract_product_features(
                text,
                product_type=active_product,
                field_definitions=product_schema["fields"],
            ) if model is not None else {}
        elif active_widget in {
            "ACCOUNT_SETUP_FORM", "JOINT_OWNER_FORM", "BENEFICIARY_CAPTURE", "PROFILE_DATA_CAPTURE"
        }:
            extracted = await extract_active_form_fields(
                text,
                widget_title=str(active_ui.get("title", "Account opening")),
                field_definitions=active_ui.get("fields", []),
            ) if model is not None else {}
        elif active_widget == "PROFILE_ASSESSMENT":
            extracted = {}
        else:
            # On the first message, capture explicitly supplied values across
            # the whole journey, not only the account-setup screen. These
            # values are staged in state and shown later as form defaults.
            extracted = await extract_account_request(text) if model is not None else {}
            if model is not None and not active_widget:
                initial_product = str(
                    extracted.get("account_type") or extracted.get("productType")
                    or state.get("product_type") or state.get("account_type") or ""
                ).upper()
                initial_risk = await extract_risk_assessment(text)
                extracted.update(initial_risk)
                if initial_product in {"BROKERAGE", "CREDIT_FACILITY"}:
                    initial_schema = build_product_feature_requirements(initial_product)
                    initial_features = await extract_product_features(
                        text,
                        product_type=initial_product,
                        field_definitions=initial_schema["fields"],
                    )
                    extracted.update(initial_features)

        if not any(str(value).strip() for value in extracted.values()):
            assistant_answer = await answer_journey_question(
                text,
                widget_title=str(active_ui.get("title", "Account opening")),
                widget_description=str(active_ui.get("description", "")),
                field_definitions=active_ui.get("fields", []),
                product_type=str(state.get("product_type", state.get("account_type", ""))),
            )

    client_id = extracted.get("client_id") or extracted.get("clientId") or extract_value(
        r"\bclient\s+([A-Z0-9-]+)", text, state.get("client_id", "C12345")
    )

    # The LLM interprets natural-language intent. Python only validates the
    # returned domain values; structured UI submissions are already explicit.
    allowed_products = {"BROKERAGE", "CREDIT_FACILITY"}
    allowed_registrations = {"INDIVIDUAL", "INDIVIDUAL_TOD", "JOINT", "JOINT_TOD"}
    raw_product = str(
        extracted.get("productType") or extracted.get("account_type") or ""
    ).strip().upper()
    raw_registration = str(
        extracted.get("registrationType") or extracted.get("ownership") or ""
    ).strip().upper()

    product_type = (
        raw_product if raw_product in allowed_products
        else state.get("product_type", "")
    )
    ownership = (
        raw_registration if raw_registration in allowed_registrations
        else state.get("ownership", "INDIVIDUAL")
    )
    owner = extracted.get("joint_owner_name") or extract_value(
        r"(?:joint owner|co-owner)(?: name)?\s*(?:is|:|to)\s*([A-Za-z][A-Za-z .'-]+?)(?:,|;|$)",
        text, state.get("joint_owner_name", "")
    )
    tax = extracted.get("joint_owner_tax_residency") or extract_value(
        r"(?:tax residency|residency)\s*(?:is|:|to)\s*([A-Za-z][A-Za-z .'-]+?)(?:,|;|$)",
        text, state.get("joint_owner_tax_residency", "")
    )
    dashboard_navigation = form_submission and extracted.get("formId") == "DASHBOARD_NAVIGATION"
    requested_section = str(extracted.get("section", "")).strip().upper() if dashboard_navigation else ""
    setup_submitted = form_submission and extracted.get("formId") == "ACCOUNT_SETUP"
    joint_owner_submission = form_submission and extracted.get("formId") == "JOINT_OWNER_DETAILS"
    if joint_owner_submission:
        missing_joint = [
            key for key in ("jointOwnerName", "jointOwnerTaxResidency")
            if not str(extracted.get(key, "")).strip()
        ]
        if missing_joint:
            raise ValueError("Joint-owner details are incomplete. Required fields: " + ", ".join(missing_joint))
    profile_confirmed = form_submission and extracted.get("formId") == "PROFILE_CONFIRMATION"
    profile_capture = form_submission and extracted.get("formId") == "PROFILE_DATA_CAPTURE"
    profile_capture_requested = form_submission and extracted.get("formId") == "PROFILE_CAPTURE_REQUEST"
    beneficiary_capture = form_submission and extracted.get("formId") == "BENEFICIARY_CAPTURE"
    beneficiary_prefill = not form_submission and active_widget == "BENEFICIARY_CAPTURE"
    profile_data_prefill = not form_submission and active_widget == "PROFILE_DATA_CAPTURE"
    beneficiary_skip = form_submission and extracted.get("formId") == "BENEFICIARY_SKIP"
    risk_assessment_submission = form_submission and extracted.get("formId") == "RISK_ASSESSMENT"
    risk_assessment_prefill = (
        not form_submission
        and state.get("ui", {}).get("widgetId") == "RISK_ASSESSMENT_FORM"
    )
    initial_journey_prefill = not form_submission and not active_widget
    product_features_submission = form_submission and extracted.get("formId") == "PRODUCT_FEATURES"
    product_features_prefill = (
        not form_submission
        and state.get("ui", {}).get("widgetId") == "PRODUCT_FEATURES_FORM"
    )
    risk_fields = ("investmentObjectives", "investmentTimeHorizon", "liquidityNeeds", "riskTolerance")
    submitted_risk = {
        key: str(extracted.get(key, "")).strip()
        for key in risk_fields
        if str(extracted.get(key, "")).strip()
    } if (risk_assessment_submission or risk_assessment_prefill or initial_journey_prefill) else {}
    if risk_assessment_submission:
        missing_risk = [key for key in risk_fields if not submitted_risk.get(key)]
        if missing_risk:
            raise ValueError("Risk assessment is incomplete. Required fields: " + ", ".join(missing_risk))
        submitted_risk["investmentObjectives"] = [
            value.strip().upper() for value in submitted_risk["investmentObjectives"].split(",") if value.strip()
        ]
        submitted_risk["riskTolerance"] = submitted_risk["riskTolerance"].upper()
        submitted_risk["investmentTimeHorizon"] = submitted_risk["investmentTimeHorizon"].upper()
        submitted_risk["liquidityNeeds"] = submitted_risk["liquidityNeeds"].upper()
        allowed_risk_values = {
            "riskTolerance": {"CONSERVATIVE", "MODERATE", "AGGRESSIVE"},
            "investmentTimeHorizon": {"UNDER_3_YEARS", "3_TO_5_YEARS", "5_TO_10_YEARS", "OVER_10_YEARS"},
            "liquidityNeeds": {"LOW", "MEDIUM", "HIGH"},
        }
        invalid_risk = [
            key for key, allowed in allowed_risk_values.items()
            if submitted_risk[key] not in allowed
        ]
        if not submitted_risk["investmentObjectives"] or invalid_risk:
            raise ValueError("Risk assessment contains invalid values: " + ", ".join(invalid_risk or ["investmentObjectives"]))
    submitted_features: dict[str, Any] = {}
    if product_features_submission or product_features_prefill or initial_journey_prefill:
        product_type_for_features = str(
            extracted.get("account_type") or extracted.get("productType")
            or state.get("product_type") or state.get("account_type") or ""
        ).upper()
        feature_schema = build_product_feature_requirements(product_type_for_features)
        feature_fields = feature_schema["fields"]
        for field in feature_fields:
            name = field["name"]
            value = str(extracted.get(name, "")).strip()
            if not value:
                if product_features_submission and field.get("required"):
                    raise ValueError("Product features are incomplete. Required fields: " + name)
                continue
            if field["type"] == "select":
                value = value.upper()
                if value not in field["options"]:
                    raise ValueError(f"Unsupported value for {name}: {value}")
            elif field["type"] == "number":
                try:
                    value = float(value.replace(",", ""))
                except ValueError as exc:
                    raise ValueError(f"{name} must be a valid number.") from exc
                if value <= 0:
                    raise ValueError(f"{name} must be greater than zero.")
            submitted_features[name] = value
    beneficiary_values = {
        key: str(extracted.get(key, "")).strip()
        for key in ("beneficiaryFullName", "beneficiaryRelationship", "beneficiaryDateOfBirth")
        if str(extracted.get(key, "")).strip()
    } if (beneficiary_capture or beneficiary_prefill) else {}
    captured_values = {
        str(key): value for key, value in extracted.items()
        if key not in {"formId", "clientId"} and value is not None and str(value).strip() != ""
    } if (profile_capture or profile_data_prefill) else {}
    explicitly_confirmed_values = {
        item["field"]: item["value"]
        for item in state.get("profile_assessment", {}).get("confirmationRequired", [])
        if item.get("field")
    } if profile_confirmed else {}
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
        "account_setup_complete": setup_submitted or state.get("account_setup_complete", False),
        "profile_confirmed": profile_confirmed or state.get("profile_confirmed", False),
        "profile_capture_requested": profile_capture_requested,
        "profile_data_submitted": profile_capture or state.get("profile_data_submitted", False),
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
            beneficiary_capture or beneficiary_skip
            or state.get("beneficiary_capture_completed", False)
        ),
        "risk_assessment": {**state.get("risk_assessment", {}), **submitted_risk},
        "risk_assessment_completed": risk_assessment_submission or state.get("risk_assessment_completed", False),
        "product_features": {**state.get("product_features", {}), **submitted_features},
        "product_features_completed": product_features_submission or state.get("product_features_completed", False),
        "joint_owner_name": str(extracted.get("jointOwnerName") or owner or state.get("joint_owner_name", "")),
        "joint_owner_tax_residency": str(extracted.get("jointOwnerTaxResidency") or tax or state.get("joint_owner_tax_residency", "")),
        "messages": [AIMessage(content=assistant_answer)] if assistant_answer else [],
        "conversation_only": bool(assistant_answer),
        "dashboard_navigation": dashboard_navigation,
        "requested_section": requested_section,
        "last_form_action": str(extracted.get("formId", "")) if form_submission else "",
    }


def build_journey_status(state: AccountOpeningState) -> dict[str, Any]:
    """Build a deterministic, UI-agnostic progress model from workflow state."""
    ui = state.get("ui", {})
    widget_id = ui.get("widgetId", "")
    profile_assessment = state.get("profile_assessment", {})
    profile_has_actions = bool(profile_assessment.get("actionRequired"))
    ownership = str(state.get("ownership", "INDIVIDUAL")).upper()
    joint_required = ownership in {"JOINT", "JOINT_TOD"}
    product_type = str(state.get("product_type") or state.get("account_type") or "").upper()
    account_missing = []
    if product_type not in {"BROKERAGE", "CREDIT_FACILITY"}:
        account_missing.append("productType")
    if ownership not in {"INDIVIDUAL", "INDIVIDUAL_TOD", "JOINT", "JOINT_TOD"}:
        account_missing.append("registrationType")
    if not str(state.get("account_nickname") or "Brokerage 1").strip():
        account_missing.append("accountNickname")
    if joint_required:
        if not str(state.get("joint_owner_name", "")).strip():
            account_missing.append("jointOwnerName")
        if not str(state.get("joint_owner_tax_residency", "")).strip():
            account_missing.append("jointOwnerTaxResidency")

    risk = state.get("risk_assessment", {})
    investment = (state.get("client_profile", {}).get("investmentProfile") or {})
    risk_values = {
        "investmentObjectives": risk.get("investmentObjectives", investment.get("investmentObjectives")),
        "investmentTimeHorizon": risk.get("investmentTimeHorizon"),
        "liquidityNeeds": risk.get("liquidityNeeds"),
        "riskTolerance": risk.get("riskTolerance", investment.get("riskTolerance")),
    }
    risk_missing = [key for key, value in risk_values.items() if value is None or value == "" or value == []]

    feature_schema = build_product_feature_requirements(product_type) if product_type in {"BROKERAGE", "CREDIT_FACILITY"} else {"fields": []}
    features = state.get("product_features", {})
    feature_missing = [
        field["name"] for field in feature_schema["fields"]
        if field.get("required")
        and (features.get(field["name"]) is None or features.get(field["name"]) == "")
        and (field.get("defaultValue") is None or field.get("defaultValue") == "")
    ]
    draft_created = widget_id == "DRAFT_CONFIRMATION"

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
    current_stage = current_by_widget.get(widget_id)

    stages = [
        {"id": "ACCOUNT_DETAILS", "label": "Account Details"},
        {"id": "PROFILE", "label": "Client Profile"},
        {"id": "RISK_PROFILE", "label": "Risk Profile"},
        {"id": "FEATURES", "label": "Features"},
        {"id": "SUMMARY", "label": "Summary"},
    ]
    statuses: dict[str, str] = {}
    statuses["PROFILE"] = (
        "ACTION_REQUIRED" if profile_has_actions else
        "COMPLETED" if profile_assessment else
        "PENDING"
    )
    statuses["ACCOUNT_DETAILS"] = "ACTION_REQUIRED" if account_missing else "COMPLETED"
    statuses["RISK_PROFILE"] = "ACTION_REQUIRED" if risk_missing else "COMPLETED"
    product_selected = bool(product_type)
    statuses["FEATURES"] = (
        "PENDING" if not product_selected else
        "ACTION_REQUIRED" if feature_missing else
        "COMPLETED"
    )
    statuses["SUMMARY"] = (
        "COMPLETED" if draft_created else
        "ACTION_REQUIRED" if all(statuses.get(key) == "COMPLETED" for key in ("PROFILE", "ACCOUNT_DETAILS", "RISK_PROFILE", "FEATURES")) else
        "PENDING"
    )

    for stage in stages:
        stage["status"] = statuses[stage["id"]]
    completed_count = sum(1 for stage in stages if stage["status"] == "COMPLETED")
    return {
        "stages": stages,
        "currentStage": current_stage,
        "completedCount": completed_count,
        "totalCount": len(stages),
        "overallStatus": "COMPLETED" if completed_count == len(stages) else "IN_PROGRESS",
        "sections": [
            {"id": stage["id"], "label": stage["label"], "status": stage["status"],
             "description": {
                 "PROFILE": "Review existing client information and complete missing mandatory details.",
                 "ACCOUNT_DETAILS": "Select product, registration and account ownership details.",
                 "RISK_PROFILE": "Review objectives, time horizon, liquidity and risk tolerance.",
                 "FEATURES": "Review product-specific elections and preferences.",
                 "SUMMARY": "Review the complete application before explicit draft approval.",
             }[stage["id"]]}
            for stage in stages
        ],
    }


def prepare_application_dashboard(state: AccountOpeningState) -> dict[str, Any]:
    """Render the dashboard as the primary workspace for the application."""
    profile = state.get("client_profile", {})
    status = build_journey_status(state)
    ui = {
        "mode": "SUMMARY",
        "widgetId": "APPLICATION_DASHBOARD",
        "title": "Account opening workspace",
        "description": "Review the status of each section. Open any section to confirm existing information or complete required fields.",
        "fields": [],
        "data": {
            "clientId": state.get("client_id", ""),
            "clientName": profile.get("displayName", ""),
            "productType": state.get("product_type", state.get("account_type", "")) or "Not selected",
            "registrationType": state.get("ownership", "INDIVIDUAL"),
            "accountNickname": state.get("account_nickname", "Brokerage 1"),
            "kycStatus": profile.get("kycStatus", "UNKNOWN"),
        },
        "approvalRequired": False,
    }
    ui["journeyStatus"] = status
    return {"ui": ui, "journey_status": status,
            "messages": [AIMessage(content="Your application workspace is ready. Select any section to review or complete it.")]}


def open_dashboard_section(state: AccountOpeningState) -> dict[str, Any]:
    """Open a requested section without advancing or completing other sections."""
    section = str(state.get("requested_section", "")).upper()
    if section == "DASHBOARD":
        return prepare_application_dashboard(state)
    if section == "PROFILE":
        return prepare_profile_assessment(state)
    if section == "ACCOUNT_DETAILS":
        ownership = str(state.get("ownership", "INDIVIDUAL")).upper()
        joint_required = ownership in {"JOINT", "JOINT_TOD"}
        joint_missing = joint_required and not (
            state.get("joint_owner_name") and state.get("joint_owner_tax_residency")
        )
        if state.get("account_setup_complete") and joint_missing:
            return {
                "ui": {
                    "mode": "FORM",
                    "widgetId": "JOINT_OWNER_FORM",
                    "title": "Joint owner information",
                    "description": "Complete the required joint-owner details for this registration.",
                    "fields": [
                        {"name": "jointOwnerName", "label": "Joint owner full name", "type": "text", "required": True, "defaultValue": state.get("joint_owner_name", "")},
                        {"name": "jointOwnerTaxResidency", "label": "Joint owner tax residency", "type": "text", "required": True, "defaultValue": state.get("joint_owner_tax_residency", "")},
                    ],
                }
            }
        return prepare_account_setup(state)
    if section == "RISK_PROFILE":
        return prepare_risk_assessment(state)
    if section == "FEATURES":
        if not state.get("product_type") and not state.get("account_type"):
            raise ValueError("Select an account product in Account Details before opening Product Features.")
        return prepare_product_features(state)
    if section == "SUMMARY":
        status = build_journey_status(state)
        incomplete = [item["label"] for item in status["sections"]
                      if item["id"] != "SUMMARY" and item["status"] != "COMPLETED"]
        if incomplete:
            dashboard = prepare_application_dashboard(state)
            dashboard["messages"] = [AIMessage(content=(
                "The application is not ready for final review. Complete these sections first: "
                + ", ".join(incomplete)
            ))]
            return dashboard
        return prepare_ui(state)
    raise ValueError(f"Unsupported application section: {section!r}")


def publish_journey_status(state: AccountOpeningState) -> dict[str, Any]:
    """Attach the same backend-calculated journey model to every rendered widget."""
    journey_status = build_journey_status(state)
    ui = dict(state.get("ui", {}))
    ui["journeyStatus"] = journey_status
    return {"ui": ui, "journey_status": journey_status}


def prepare_account_setup(state: AccountOpeningState) -> dict[str, Any]:
    ui = {
        "mode": "FORM",
        "widgetId": "ACCOUNT_SETUP_FORM",
        "title": "Set up your account",
        "description": "Confirm the product, registration and account preferences to begin.",
        "fields": [
            {"name": "productType", "label": "Product type", "type": "select", "required": True, "options": ["BROKERAGE", "CREDIT_FACILITY"], "defaultValue": state.get("product_type", "")},
            {"name": "registrationType", "label": "Registration type", "type": "select", "required": True, "options": ["INDIVIDUAL", "INDIVIDUAL_TOD", "JOINT", "JOINT_TOD"], "defaultValue": state.get("ownership", "INDIVIDUAL")},
            {"name": "accountNickname", "label": "Account nickname", "type": "text", "required": True, "placeholder": "Account nickname", "defaultValue": state.get("account_nickname") or "Brokerage 1"},
            {"name": "marginOption", "label": "Margin option", "type": "select", "required": True, "options": ["NONE", "MARGIN"], "defaultValue": state.get("margin_option", "NONE")},
        ],
        "data": {"clientId": state.get("client_id", "C12345")}
    }
    return {"ui": ui, "messages": [AIMessage(content="Let's confirm the account setup. I'll retrieve the existing client profile after you continue.")]}


def route_after_setup(state: AccountOpeningState) -> str:
    if state.get("conversation_only"):
        return "stay"
    if state.get("dashboard_navigation"):
        return "open_section"
    if state.get("profile_capture_requested"):
        return "capture_profile"
    if not state.get("client_profile") or state.get("profile_data_submitted"):
        return "retrieve_client"
    return "dashboard"


async def retrieve_client(
    state: AccountOpeningState,
    client_api: Any | None = None,
) -> dict[str, Any]:
    """Retrieve the authoritative client profile through the Experience API adapter."""
    client_id = state.get("client_id", "C12345")
    if client_api is None:
        raise RuntimeError("Client Experience API adapter was not configured.")
    profile = await client_api.get_client_profile(client_id)
    return {"client_profile": profile}




def assess_client_profile(state: AccountOpeningState) -> dict[str, Any]:
    """Classify profile completeness using deterministic required-field rules.

    Confirmed values are held separately from the source profile. The source
    response is never mutated by application-level corrections.
    """
    profile = state.get("client_profile", {})
    confirmed = state.get("confirmed_profile_data", {})
    personal = profile.get("personalDetails") or {}
    residential = (profile.get("addresses") or {}).get("residential") or {}
    tax_residencies = profile.get("taxResidencies") or []
    tax = tax_residencies[0] if tax_residencies else {}
    employment = profile.get("employment") or {}
    investment = profile.get("investmentProfile") or {}
    definitions = [
        ("Personal details", personal, ["firstName", "lastName", "dateOfBirth", "email", "phone"],
         {"firstName", "lastName", "dateOfBirth", "email", "phone"}),
        ("Residential address", residential, ["line1", "line2", "city", "state", "postalCode", "country"],
         {"line1", "city", "postalCode", "country"}),
        ("Tax residency", tax, ["country", "taxIdType", "taxIdMasked", "status"], {"country"}),
        ("Employment", employment, ["status", "occupation", "employerName", "industry"], {"status", "occupation"}),
        ("Investment profile", investment, ["experienceLevel", "investmentObjectives", "riskTolerance", "annualIncomeRange", "netWorthRange"],
         {"experienceLevel", "investmentObjectives", "riskTolerance"}),
    ]
    completed = [
        {"label": "Client identity", "value": f"{profile.get('displayName', '')} ({profile.get('clientId', '')})"},
        {"label": "KYC status (retrieved; not an approval)", "value": str(profile.get("kycStatus", "UNKNOWN"))},
    ]
    confirmations: list[dict[str, str]] = []
    actions: list[dict[str, str]] = []
    sections: list[dict[str, Any]] = []
    for name, values, fields, required in definitions:
        rows: list[dict[str, str]] = []
        missing_required = False
        for field in fields:
            path = f"{name}|{field}"
            value = confirmed.get(path, values.get(field))
            present = value is not None and value != "" and value != []
            label = field.replace("firstName", "First name").replace("lastName", "Last name").replace("dateOfBirth", "Date of birth").replace("taxIdType", "Tax ID type").replace("taxIdMasked", "Tax ID").replace("investmentObjectives", "Investment objectives")
            display = ", ".join(map(str, value)) if isinstance(value, list) else (str(value) if present else "Not provided")
            rows.append({"name": field, "label": label, "value": display,
                         "required": field in required, "missing": field in required and not present})
            if present:
                confirmations.append({"label": f"{name}: {label}", "value": display, "field": path, "required": field in required})
            elif field in required:
                missing_required = True
                actions.append({"label": f"{name}: {label}", "value": "Required", "field": path, "required": True})
        sections.append({"name": name, "status": "ACTION_REQUIRED" if missing_required else "CONFIRMATION_REQUIRED" if any(r["value"] != "Not provided" for r in rows) else "NOT_PROVIDED", "fields": rows})
    return {"profile_assessment": {"completed": completed, "confirmationRequired": confirmations,
            "actionRequired": actions, "sections": sections, "isComplete": not actions}}
    
def prepare_profile_capture(state: AccountOpeningState) -> dict[str, Any]:
    """Build a form containing only profile fields that need confirmation or completion."""
    assessment = state.get("profile_assessment", {})
    fields: list[dict[str, Any]] = []
    confirmed = state.get("confirmed_profile_data", {})
    for item in assessment.get("confirmationRequired", []) + assessment.get("actionRequired", []):
        fields.append({
            "name": item["field"],
            "label": item["label"],
            "type": "text",
            "required": bool(item.get("required")),
            "placeholder": "Enter value" if item.get("value") == "Required" else "Confirm or correct the retrieved value",
            "defaultValue": "" if item.get("value") == "Required" else str(item.get("value", "")),
        })
    ui = {
        "mode": "FORM",
        "widgetId": "PROFILE_DATA_CAPTURE",
        "title": "Confirm or complete client information",
        "description": "Only missing mandatory and populated confirmation-required fields are shown. Your entries are stored as application data; the source client profile is not overwritten.",
        "fields": fields,
        "data": {"clientId": state.get("client_id", "")},
    }
    return {"ui": ui, "messages": [AIMessage(content="Please confirm or correct the populated fields and complete the mandatory fields shown.")]}


def prepare_profile_assessment(state: AccountOpeningState) -> dict[str, Any]:
    assessment = state.get("profile_assessment", {})
    ui = {"mode": "SUMMARY", "widgetId": "PROFILE_ASSESSMENT",
          "title": "Review existing client profile",
          "description": "Review the information retrieved from the Client Experience API. Confirm it before continuing.",
          "fields": [], "data": assessment, "approvalRequired": False}
    return {"ui": ui, "messages": [AIMessage(content=(
        f"Client profile retrieved. {len(assessment.get('confirmationRequired', []))} attributes need confirmation; "
        f"{len(assessment.get('actionRequired', []))} required attributes need attention."
    ))]}

def determine_requirements(state: AccountOpeningState) -> dict[str, Any]:
    """Resolve the registration-specific requirement matrix.

    This node classifies requirements only. Primary-owner data and client-profile
    confirmation are handled by the profile gate; joint-owner capture is conditional,
    and optional beneficiary capture follows when owner requirements are satisfied.
    Risk-assessment capture remains a later mandatory journey gate.
    """
    registration_type = state.get("ownership", "INDIVIDUAL")
    requirements = build_registration_requirements(registration_type)

    missing: list[str] = []
    joint_requirement = next(
        item for item in requirements["requirements"]
        if item["key"] == "JOINT_OWNER_DETAILS"
    )
    if joint_requirement["required"]:
        if not state.get("joint_owner_name"):
            missing.append("jointOwnerName")
        if not state.get("joint_owner_tax_residency"):
            missing.append("jointOwnerTaxResidency")

    return {
        "missing_fields": missing,
        "requirements_assessment": requirements,
    }


def prepare_risk_assessment(state: AccountOpeningState) -> dict[str, Any]:
    """Collect and confirm mandatory risk-profile inputs; do not score suitability."""
    profile = state.get("client_profile", {})
    investment = profile.get("investmentProfile") or {}
    current = state.get("risk_assessment", {})
    objectives = current.get("investmentObjectives")
    if objectives is None:
        objectives = investment.get("investmentObjectives", [])
    if isinstance(objectives, list):
        objectives = ", ".join(str(value) for value in objectives)
    risk_tolerance = current.get("riskTolerance") or investment.get("riskTolerance") or profile.get("riskProfile", "")
    fields = [
        {"name": "investmentObjectives", "label": "Investment objectives (comma-separated)", "type": "text", "required": True, "defaultValue": str(objectives or ""), "placeholder": "e.g. GROWTH, INCOME"},
        {"name": "riskTolerance", "label": "Risk comfort level", "type": "select", "required": True, "options": ["CONSERVATIVE", "MODERATE", "AGGRESSIVE"], "defaultValue": risk_tolerance},
        {"name": "investmentTimeHorizon", "label": "Investment time horizon", "type": "select", "required": True, "options": ["UNDER_3_YEARS", "3_TO_5_YEARS", "5_TO_10_YEARS", "OVER_10_YEARS"], "defaultValue": current.get("investmentTimeHorizon", "")},
        {"name": "liquidityNeeds", "label": "Liquidity needs", "type": "select", "required": True, "options": ["LOW", "MEDIUM", "HIGH"], "defaultValue": current.get("liquidityNeeds", "")},
    ]
    ui = {
        "mode": "FORM",
        "widgetId": "RISK_ASSESSMENT_FORM",
        "title": "Investment risk assessment",
        "description": "Confirm the existing investment profile and complete the remaining required information. This step records client-provided information; it does not determine suitability or recommend investments.",
        "fields": fields,
        "data": {"clientId": state.get("client_id", ""), "mandatory": True},
    }
    return {"ui": ui, "messages": [AIMessage(content="Please confirm the existing investment profile and complete all required risk-assessment fields.")]}


def prepare_product_features(state: AccountOpeningState) -> dict[str, Any]:
    """Render the product-specific feature form from deterministic requirements."""
    product_type = state.get("product_type", state.get("account_type", ""))
    schema = build_product_feature_requirements(product_type)
    existing = state.get("product_features", {})
    fields = []
    for definition in schema["fields"]:
        field = dict(definition)
        default_value = existing.get(field["name"], field.get("defaultValue", ""))
        field["defaultValue"] = str(default_value)
        fields.append(field)
    title = "Brokerage features" if product_type == "BROKERAGE" else "Credit facility details"
    description = (
        "Capture brokerage account preferences. Detailed option sets and business rules remain with the relevant product and downstream services."
        if product_type == "BROKERAGE"
        else "Provide the requested facility amount, proposed collateral and intended purpose. These are requests only and do not represent credit approval or collateral acceptance."
    )
    ui = {
        "mode": "FORM",
        "widgetId": "PRODUCT_FEATURES_FORM",
        "title": title,
        "description": description,
        "fields": fields,
        "data": {"productType": product_type, "mandatory": True},
    }
    return {"ui": ui, "messages": [AIMessage(content=f"Please complete the required {product_type.replace('_', ' ').lower()} product details.")]}


def prepare_beneficiary_capture(state: AccountOpeningState) -> dict[str, Any]:
    """Offer an optional single-beneficiary capture step for every registration."""
    beneficiary = state.get("beneficiary_data", {})
    ui = {
        "mode": "FORM",
        "widgetId": "BENEFICIARY_CAPTURE",
        "title": "Beneficiary details (optional)",
        "description": "You may add one beneficiary now or skip this step and continue. Beneficiary details are optional for every supported registration type in this POC.",
        "fields": [
            {"name": "beneficiaryFullName", "label": "Beneficiary full name", "type": "text", "required": False, "defaultValue": beneficiary.get("beneficiaryFullName", ""), "placeholder": "Full name"},
            {"name": "beneficiaryRelationship", "label": "Relationship to account owner", "type": "text", "required": False, "defaultValue": beneficiary.get("beneficiaryRelationship", ""), "placeholder": "e.g. spouse, child"},
            {"name": "beneficiaryDateOfBirth", "label": "Beneficiary date of birth", "type": "date", "required": False, "defaultValue": beneficiary.get("beneficiaryDateOfBirth", "")},
        ],
        "data": {"clientId": state.get("client_id", ""), "optional": True},
    }
    return {"ui": ui, "messages": [AIMessage(content="Beneficiary details are optional. Add them if available, or skip to continue.") ]}


def build_application_review_sections(state: AccountOpeningState) -> list[dict[str, Any]]:
    """Build read-only, section-grouped review data for the final application summary."""
    profile = state.get("client_profile", {})
    assessment = state.get("profile_assessment", {})
    ownership = str(state.get("ownership", "INDIVIDUAL")).upper()
    product_type = str(state.get("product_type") or state.get("account_type") or "")
    risk = state.get("risk_assessment", {})
    investment = profile.get("investmentProfile") or {}
    features = state.get("product_features", {})
    sections: list[dict[str, Any]] = []

    def field(label: str, value: Any, required: bool = False) -> dict[str, Any]:
        present = value is not None and value != "" and value != []
        if isinstance(value, list):
            display = ", ".join(str(item) for item in value) if value else "Not provided"
        else:
            display = str(value) if present else "Not provided"
        return {"label": label, "value": display, "required": required,
                "missing": required and not present}

    account_fields = [
        field("Product type", product_type, True),
        field("Registration type", ownership, True),
        field("Account nickname", state.get("account_nickname") or "Brokerage 1", True),
        field("Margin option", state.get("margin_option", "NONE")),
    ]
    if ownership in {"JOINT", "JOINT_TOD"}:
        account_fields.extend([
            field("Joint owner full name", state.get("joint_owner_name"), True),
            field("Joint owner tax residency", state.get("joint_owner_tax_residency"), True),
        ])
    beneficiary = state.get("beneficiary_data", {})
    account_fields.extend([
        field("Beneficiary full name", beneficiary.get("beneficiaryFullName")),
        field("Beneficiary relationship", beneficiary.get("beneficiaryRelationship")),
        field("Beneficiary date of birth", beneficiary.get("beneficiaryDateOfBirth")),
    ])
    sections.append({"id": "ACCOUNT_DETAILS", "label": "Account Details",
                     "status": "ACTION_REQUIRED" if any(x["missing"] for x in account_fields) else "COMPLETED",
                     "fields": account_fields})

    profile_fields: list[dict[str, Any]] = [
        field("Client name", profile.get("displayName"), True),
        field("Client ID", profile.get("clientId"), True),
        field("KYC status", profile.get("kycStatus")),
    ]
    for group in assessment.get("sections", []):
        for item in group.get("fields", []):
            profile_fields.append({
                "label": f"{group.get('name', 'Profile')} · {item.get('label', '')}",
                "value": item.get("value", "Not provided"),
                "required": bool(item.get("required")),
                "missing": bool(item.get("missing")),
            })
    sections.append({"id": "PROFILE", "label": "Client Profile",
                     "status": "ACTION_REQUIRED" if profile_has_missing(profile_fields) else "COMPLETED",
                     "fields": profile_fields})

    risk_values = {
        "investmentObjectives": risk.get("investmentObjectives", investment.get("investmentObjectives")),
        "investmentTimeHorizon": risk.get("investmentTimeHorizon"),
        "liquidityNeeds": risk.get("liquidityNeeds"),
        "riskTolerance": risk.get("riskTolerance", investment.get("riskTolerance")),
    }
    risk_fields = [
        field("Investment objectives", risk_values["investmentObjectives"], True),
        field("Investment time horizon", risk_values["investmentTimeHorizon"], True),
        field("Liquidity needs", risk_values["liquidityNeeds"], True),
        field("Risk tolerance", risk_values["riskTolerance"], True),
    ]
    sections.append({"id": "RISK_PROFILE", "label": "Risk Assessment",
                     "status": "ACTION_REQUIRED" if any(x["missing"] for x in risk_fields) else "COMPLETED",
                     "fields": risk_fields})

    feature_schema = build_product_feature_requirements(product_type) if product_type in {"BROKERAGE", "CREDIT_FACILITY"} else {"fields": []}
    feature_fields = [
        field(definition["label"],
              features.get(definition["name"], definition.get("defaultValue")),
              bool(definition.get("required")))
        for definition in feature_schema["fields"]
    ]
    sections.append({"id": "FEATURES", "label": "Product Features",
                     "status": "PENDING" if not product_type else
                     "ACTION_REQUIRED" if any(x["missing"] for x in feature_fields) else "COMPLETED",
                     "fields": feature_fields})
    return sections


def profile_has_missing(fields: list[dict[str, Any]]) -> bool:
    return any(item.get("missing") for item in fields)


def prepare_ui(state: AccountOpeningState) -> dict[str, Any]:
    if state.get("missing_fields"):
        ui = {
            "mode": "FORM",
            "widgetId": "JOINT_OWNER_FORM",
            "title": "Joint owner information",
            "description": "Complete the required information before reviewing the application.",
            "fields": [
                {
                    "name": "jointOwnerName",
                    "label": "Joint owner full name",
                    "type": "text",
                    "required": True,
                    "placeholder": "e.g. Jordan Morgan",
                    "defaultValue": state.get("joint_owner_name", ""),
                },
                {
                    "name": "jointOwnerTaxResidency",
                    "label": "Joint owner tax residency",
                    "type": "text",
                    "required": True,
                    "placeholder": "e.g. Singapore",
                    "defaultValue": state.get("joint_owner_tax_residency", ""),
                },
            ],
        }
        message = (
            f"I found client {state['client_profile']['displayName']} ({state['client_id']}). "
            f"The client profile reports KYC status {state['client_profile'].get('kycStatus', 'UNKNOWN')}. Please provide the joint owner's name and tax residency."
        )
        return {"ui": ui, "approval_status": "", "messages": [AIMessage(content=message)]}

    profile = state.get("client_profile", {})
    revision = int(state.get("review_revision", 0)) + 1
    ui = {
        "mode": "SUMMARY",
        "widgetId": "APPLICATION_SUMMARY",
        "title": "Review application details",
        "description": "Review the latest details. Any change requires a fresh confirmation.",
        "fields": [],
        "data": {
            "clientId": state.get("client_id", ""),
            "clientName": profile.get("displayName", ""),
            "accountType": state.get("account_type", ""),
            "productType": state.get("product_type", state.get("account_type", "")),
            "accountNickname": state.get("account_nickname", ""),
            "marginOption": state.get("margin_option", "NONE"),
            "ownership": state.get("ownership", ""),
            "jointOwnerName": state.get("joint_owner_name", "") or "—",
            "jointOwnerTaxResidency": state.get("joint_owner_tax_residency", "") or "—",
            "beneficiaryName": state.get("beneficiary_data", {}).get("beneficiaryFullName", "Not provided"),
            "beneficiaryRelationship": state.get("beneficiary_data", {}).get("beneficiaryRelationship", "Not provided"),
            "riskAssessment": state.get("risk_assessment", {}),
        "productFeatures": state.get("product_features", {}),
            "productFeatures": state.get("product_features", {}),
            "kycStatus": profile.get("kycStatus", "UNKNOWN"),
            "requirements": "; ".join(
                f"{item['label']}: {item['status']}"
                for item in state.get("requirements_assessment", {}).get("requirements", [])
            ),
            "reviewVersion": revision,
            "reviewSections": build_application_review_sections(state),
        },
        "approvalRequired": True,
    }
    message = "Here is the current application summary. You can request a change or explicitly confirm or reject it."
    return {
        "ui": ui,
        "approval_status": "PENDING",
        "review_action": "",
        "review_revision": revision,
        "draft_idempotency_key": uuid.uuid4().hex,
        "messages": [AIMessage(content=message)],
    }


def regex_edit_extraction(text: str) -> dict[str, str]:
    """Small deterministic fallback for common conversational edits."""
    patterns = {
        "client_id": r"\bclient\s+(?:id\s+)?([A-Z0-9-]+)",
        "account_type": r"account type\s+(?:to|is)\s+(BROKERAGE|CASH|MARGIN)",
        "ownership": r"ownership\s+(?:to|is)\s+(JOINT|INDIVIDUAL)",
        "joint_owner_name": r"(?:joint owner|co-owner)(?: name)?\s+(?:to|is)\s+([A-Za-z][A-Za-z .'-]+?)(?:\.|,|;|$)",
        "joint_owner_tax_residency": r"(?:joint owner(?:'s)? )?tax residency\s+(?:to|is)\s+([A-Za-z][A-Za-z .'-]+?)(?:\.|,|;|$)",
    }
    return {
        key: extract_value(pattern, text)
        for key, pattern in patterns.items()
        if re.search(pattern, text, re.IGNORECASE)
    }


async def apply_review_edit(state: AccountOpeningState, decision: dict[str, Any]) -> dict[str, Any]:
    text = str(decision.get("message", "")).strip()
    extracted: dict[str, Any] = {}
    if model is not None and text:
        extracted = await extract_account_request(text)

    # Fill only fields explicitly extracted from this edit request; retain all others.
    fallback = regex_edit_extraction(text)
    updates: dict[str, str] = {}
    for key in EDITABLE_FIELDS:
        value = str(extracted.get(key) or fallback.get(key) or "").strip()
        if value:
            updates[EDITABLE_FIELDS[key]] = value.upper() if key in {
                "account_type", "ownership"
            } else value

    if not updates:
        return {
            "approval_status": "PENDING",
            "review_action": "EDIT",
            "messages": [AIMessage(content="I couldn't identify a specific field change. Please specify the field and its new value, for example: 'Change the account nickname to Brokerage 2'.")],
        }

    # Restrict values to supported POC values. Enterprise APIs remain authoritative.
    if "ownership" in updates and updates["ownership"] not in {"JOINT", "JOINT_TOD", "INDIVIDUAL", "INDIVIDUAL_TOD"}:
        updates.pop("ownership")
    if "account_type" in updates and updates["account_type"] not in {"BROKERAGE", "CREDIT_FACILITY"}:
        updates.pop("account_type")

    if not updates:
        return {
            "approval_status": "PENDING",
            "review_action": "EDIT",
            "messages": [AIMessage(content="That value is not supported by this POC. Please use a supported product type or registration type.")],
        }

    logger_message = ", ".join(f"{key}={value}" for key, value in updates.items())
    return {
        **updates,
        "approval_status": "PENDING",
        "review_action": "EDIT",
        "application": {},
        "messages": [AIMessage(content=f"I've updated the requested details ({logger_message}). Rechecking the application and preparing a new summary. Your previous review is no longer valid.")],
    }


async def await_human_approval(state: AccountOpeningState) -> dict[str, Any]:
    # No side effects occur before interrupt; LangGraph may re-run this node on resume.
    if state.get("approval_status") != "PENDING":
        raise ValueError("There is no pending application review to resume.")

    decision = interrupt({
        "kind": "ACCOUNT_OPENING_REVIEW",
        "message": "You can request a change, confirm the draft or reject the application.",
        "application": state.get("ui", {}).get("data", {}),
        "reviewVersion": state.get("review_revision", 1),
    })

    if isinstance(decision, dict) and decision.get("action") == "APPROVE" and decision.get("approved") is True:
        return {
            "approval_status": "APPROVED",
            "review_action": "APPROVE",
            "messages": [AIMessage(content="Application review confirmed. Sending the approved application to the Draft Application API.")],
        }

    if isinstance(decision, dict) and decision.get("action") == "EDIT":
        return await apply_review_edit(state, decision)

    return {
        "approval_status": "REJECTED",
        "review_action": "REJECT",
        "ui": {
            "mode": "ALERT",
            "widgetId": "INFORMATION_ALERT",
            "title": "Application not approved",
            "description": "No draft was created. Start a new account-opening request if you want to make changes and review again.",
            "fields": [],
            "data": {"status": "REJECTED"},
        },
        "messages": [AIMessage(content="The application was not approved. No draft was created.")],
    }


async def create_draft(
    state: AccountOpeningState,
    draft_api: Any | None = None,
) -> dict[str, Any]:
    """Call the authoritative Draft Application API only after explicit approval."""
    if state.get("approval_status") != "APPROVED":
        raise ValueError("Draft creation blocked: explicit application approval is required.")
    if draft_api is None:
        raise RuntimeError("Draft Application API adapter was not configured.")

    idempotency_key = state.get("draft_idempotency_key")
    if not idempotency_key:
        raise ValueError("Draft creation blocked: idempotency key is missing.")

    application_request: dict[str, Any] = {
        "clientId": state["client_id"],
        "accountType": state["account_type"],
        "productType": state.get("product_type", state["account_type"]),
        "registrationType": state["ownership"],
        "accountNickname": state.get("account_nickname", ""),
        "marginOption": state.get("margin_option", "NONE"),
        "ownership": state["ownership"],
        "applicationData": state.get("application_data", {}),
        "riskAssessment": state.get("risk_assessment", {}),
    }
    if state.get("ownership") in {"JOINT", "JOINT_TOD"}:
        application_request["jointOwner"] = {
            "name": state.get("joint_owner_name", ""),
            "taxResidency": state.get("joint_owner_tax_residency", ""),
        }
    beneficiary = state.get("beneficiary_data", {})
    if beneficiary:
        application_request["beneficiaries"] = [{
            "fullName": beneficiary.get("beneficiaryFullName", ""),
            "relationship": beneficiary.get("beneficiaryRelationship", ""),
            "dateOfBirth": beneficiary.get("beneficiaryDateOfBirth", ""),
        }]

    draft = await draft_api.create_draft(application_request, idempotency_key)
    logger_message = (
        f"Account-opening draft {draft['applicationId']} was created successfully. "
        "The Draft Application API returned the authoritative draft identifier and status."
    )
    return {
        "application": draft,
        "ui": {
            "mode": "COMPLETE",
            "widgetId": "DRAFT_CONFIRMATION",
            "title": "Draft created",
            "description": (
                "A mock draft was created by the local adapter."
                if getattr(draft_api, "mode", "mock") == "mock"
                else "A draft was created by the Java Draft Application Experience API. No account has been submitted or opened."
            ),
            "fields": [],
            "data": {
                "applicationId": draft["applicationId"],
                "status": draft["status"],
                "clientId": draft["clientId"],
            },
        },
        "messages": [AIMessage(content=logger_message)],
    }

def route_after_requirements(state: AccountOpeningState) -> str:
    return "wait_for_input" if state.get("missing_fields") else "await_approval"


def route_after_approval(state: AccountOpeningState) -> str:
    if state.get("approval_status") == "APPROVED":
        return "create_draft"
    if state.get("approval_status") == "PENDING" and state.get("review_action") == "EDIT":
        return "revalidate"
    return "finish"


def build_graph(
    checkpointer_override: Any | None = None,
    client_api: Any | None = None,
    draft_api: Any | None = None,
):
    workflow = StateGraph(AccountOpeningState)
    workflow.add_node("understand_request", understand_request)
    workflow.add_node("prepare_account_setup", prepare_account_setup)
    workflow.add_node("prepare_application_dashboard", prepare_application_dashboard)
    workflow.add_node("open_dashboard_section", open_dashboard_section)
    workflow.add_node("publish_journey_status", publish_journey_status)
    async def retrieve_client_node(state: AccountOpeningState) -> dict[str, Any]:
        return await retrieve_client(state, client_api)

    workflow.add_node("retrieve_client", retrieve_client_node)
    workflow.add_node("assess_client_profile", assess_client_profile)
    workflow.add_node("prepare_profile_assessment", prepare_profile_assessment)
    workflow.add_node("prepare_profile_capture", prepare_profile_capture)
    workflow.add_node("prepare_beneficiary_capture", prepare_beneficiary_capture)
    workflow.add_node("prepare_risk_assessment", prepare_risk_assessment)
    workflow.add_node("prepare_product_features", prepare_product_features)
    workflow.add_node("determine_requirements", determine_requirements)
    workflow.add_node("prepare_ui", prepare_ui)
    workflow.add_node("await_approval", await_human_approval)
    async def create_draft_node(state: AccountOpeningState) -> dict[str, Any]:
        return await create_draft(state, draft_api)

    workflow.add_node("create_draft", create_draft_node)

    workflow.add_edge(START, "understand_request")
    workflow.add_conditional_edges(
        "understand_request", route_after_setup,
        {"show_setup": "prepare_account_setup", "retrieve_client": "retrieve_client",
         "dashboard": "prepare_application_dashboard", "open_section": "open_dashboard_section",
         "continue_journey": "prepare_application_dashboard", "capture_profile": "prepare_profile_capture",
         "stay": END},
    )
    workflow.add_edge("prepare_account_setup", "publish_journey_status")
    workflow.add_edge("retrieve_client", "assess_client_profile")
    workflow.add_edge("assess_client_profile", "prepare_application_dashboard")
    workflow.add_edge("prepare_application_dashboard", END)
    workflow.add_edge("open_dashboard_section", "publish_journey_status")
    workflow.add_edge("prepare_profile_assessment", "publish_journey_status")
    workflow.add_edge("prepare_profile_capture", "publish_journey_status")
    def route_after_data_requirements(state: AccountOpeningState) -> str:
        if state.get("missing_fields"):
            return "joint_owner"
        if not state.get("beneficiary_capture_completed"):
            return "beneficiary"
        if not state.get("risk_assessment_completed"):
            return "risk_assessment"
        if not state.get("product_features_completed"):
            return "product_features"
        return "review"

    workflow.add_conditional_edges(
        "determine_requirements", route_after_data_requirements,
        {"joint_owner": "prepare_ui", "beneficiary": "prepare_beneficiary_capture", "risk_assessment": "prepare_risk_assessment", "product_features": "prepare_product_features", "review": "prepare_ui"},
    )
    workflow.add_edge("prepare_beneficiary_capture", "publish_journey_status")
    workflow.add_edge("prepare_risk_assessment", "publish_journey_status")
    workflow.add_edge("prepare_product_features", "publish_journey_status")
    workflow.add_edge("prepare_ui", "publish_journey_status")
    def route_after_status(state: AccountOpeningState) -> str:
        return "await_approval" if state.get("ui", {}).get("widgetId") == "APPLICATION_SUMMARY" else "finish"

    workflow.add_conditional_edges(
        "publish_journey_status", route_after_status,
        {"finish": END, "await_approval": "await_approval"},
    )
    workflow.add_conditional_edges(
        "await_approval", route_after_approval,
        {"create_draft": "create_draft", "revalidate": "retrieve_client", "finish": END},
    )
    workflow.add_edge("create_draft", "publish_journey_status")
    saver = checkpointer if checkpointer_override is None else checkpointer_override
    return workflow.compile(checkpointer=saver)

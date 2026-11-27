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
from model_client import extract_account_request, model


class AccountOpeningState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    client_id: str
    account_type: str
    ownership: str
    base_currency: str
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


EDITABLE_FIELDS = {
    "client_id": "client_id",
    "account_type": "account_type",
    "ownership": "ownership",
    "base_currency": "base_currency",
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
    elif model is not None and text:
        extracted = await extract_account_request(text)

    client_id = extracted.get("client_id") or extract_value(
        r"\bclient\s+([A-Z0-9-]+)", text, state.get("client_id", "C12345")
    )
    account_type = extracted.get("account_type") or (
        "BROKERAGE" if "brokerage" in text.lower() else state.get("account_type", "BROKERAGE")
    )
    ownership = extracted.get("ownership") or (
        "JOINT" if "joint" in text.lower() else state.get("ownership", "INDIVIDUAL")
    )
    currency = extracted.get("base_currency") or extract_value(
        r"\b(USD|EUR|GBP|SGD|HKD|AED)\b", text, state.get("base_currency", "USD")
    )
    owner = extracted.get("joint_owner_name") or extract_value(
        r"(?:joint owner|co-owner)(?: name)?\s*(?:is|:|to)\s*([A-Za-z][A-Za-z .'-]+?)(?:,|;|$)",
        text, state.get("joint_owner_name", "")
    )
    tax = extracted.get("joint_owner_tax_residency") or extract_value(
        r"(?:tax residency|residency)\s*(?:is|:|to)\s*([A-Za-z][A-Za-z .'-]+?)(?:,|;|$)",
        text, state.get("joint_owner_tax_residency", "")
    )
    setup_submitted = form_submission and extracted.get("formId") == "ACCOUNT_SETUP"
    return {
        "client_id": str(extracted.get("clientId") or client_id),
        "account_type": str(extracted.get("productType") or account_type).upper(),
        "product_type": str(extracted.get("productType") or state.get("product_type", account_type)).upper(),
        "ownership": str(extracted.get("registrationType") or ownership).upper(),
        "base_currency": str(extracted.get("baseCurrency") or currency).upper(),
        "account_nickname": str(extracted.get("accountNickname") or state.get("account_nickname", "")),
        "margin_option": str(extracted.get("marginOption") or state.get("margin_option", "NONE")).upper(),
        "account_setup_complete": setup_submitted or state.get("account_setup_complete", False),
        "joint_owner_name": str(extracted.get("jointOwnerName") or owner or state.get("joint_owner_name", "")),
        "joint_owner_tax_residency": str(extracted.get("jointOwnerTaxResidency") or tax or state.get("joint_owner_tax_residency", "")),
    }


def prepare_account_setup(state: AccountOpeningState) -> dict[str, Any]:
    ui = {
        "mode": "FORM",
        "widgetId": "ACCOUNT_SETUP_FORM",
        "title": "Set up brokerage account",
        "description": "Confirm the product, registration and account preferences to begin.",
        "fields": [
            {"name": "productType", "label": "Product type", "type": "select", "required": True, "options": ["BROKERAGE", "INVESTMENT"], "defaultValue": state.get("product_type", "BROKERAGE")},
            {"name": "registrationType", "label": "Registration type", "type": "select", "required": True, "options": ["INDIVIDUAL", "INDIVIDUAL_TOD", "JOINT", "JOINT_TOD"], "defaultValue": state.get("ownership", "INDIVIDUAL")},
            {"name": "accountNickname", "label": "Account nickname", "type": "text", "required": True, "placeholder": "Account nickname", "defaultValue": state.get("account_nickname", "Alex Morgan - Brokerage")},
            {"name": "marginOption", "label": "Margin option", "type": "select", "required": True, "options": ["NONE", "MARGIN"], "defaultValue": state.get("margin_option", "NONE")},
            {"name": "baseCurrency", "label": "Base currency", "type": "select", "required": True, "options": ["USD", "SGD", "EUR", "GBP", "HKD", "AED"], "defaultValue": state.get("base_currency", "USD")}
        ],
        "data": {"clientId": state.get("client_id", "C12345")}
    }
    return {"ui": ui, "messages": [AIMessage(content="Let's confirm the account setup. I'll retrieve the existing client profile after you continue.")]}


def route_after_setup(state: AccountOpeningState) -> str:
    return "retrieve_client" if state.get("account_setup_complete") else "show_setup"


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


def determine_requirements(state: AccountOpeningState) -> dict[str, Any]:
    missing: list[str] = []
    if state.get("ownership") in {"JOINT", "JOINT_TOD"}:
        if not state.get("joint_owner_name"):
            missing.append("jointOwnerName")
        if not state.get("joint_owner_tax_residency"):
            missing.append("jointOwnerTaxResidency")
    return {"missing_fields": missing}


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
                },
                {
                    "name": "jointOwnerTaxResidency",
                    "label": "Joint owner tax residency",
                    "type": "text",
                    "required": True,
                    "placeholder": "e.g. Singapore",
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
            "baseCurrency": state.get("base_currency", ""),
            "jointOwnerName": state.get("joint_owner_name", "") or "—",
            "jointOwnerTaxResidency": state.get("joint_owner_tax_residency", "") or "—",
            "kycStatus": profile.get("kycStatus", "UNKNOWN"),
            "reviewVersion": revision,
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
        "base_currency": r"(?:base )?currency\s+(?:to|is)\s+(USD|EUR|GBP|SGD|HKD|AED)",
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
                "account_type", "ownership", "base_currency"
            } else value

    if not updates:
        return {
            "approval_status": "PENDING",
            "review_action": "EDIT",
            "messages": [AIMessage(content="I couldn't identify a specific field change. Please specify the field and its new value, for example: 'Change the base currency to SGD'.")],
        }

    # Restrict values to supported POC values. Enterprise APIs remain authoritative.
    if "ownership" in updates and updates["ownership"] not in {"JOINT", "INDIVIDUAL"}:
        updates.pop("ownership")
    if "account_type" in updates and updates["account_type"] not in {"BROKERAGE", "CASH", "MARGIN"}:
        updates.pop("account_type")
    if "base_currency" in updates and updates["base_currency"] not in {"USD", "EUR", "GBP", "SGD", "HKD", "AED"}:
        updates.pop("base_currency")

    if not updates:
        return {
            "approval_status": "PENDING",
            "review_action": "EDIT",
            "messages": [AIMessage(content="That value is not supported by this POC. Please use a supported account type, ownership or currency.")],
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
        "baseCurrency": state["base_currency"],
    }
    if state.get("ownership") == "JOINT":
        application_request["jointOwner"] = {
            "name": state.get("joint_owner_name", ""),
            "taxResidency": state.get("joint_owner_tax_residency", ""),
        }

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
    async def retrieve_client_node(state: AccountOpeningState) -> dict[str, Any]:
        return await retrieve_client(state, client_api)

    workflow.add_node("retrieve_client", retrieve_client_node)
    workflow.add_node("determine_requirements", determine_requirements)
    workflow.add_node("prepare_ui", prepare_ui)
    workflow.add_node("await_approval", await_human_approval)
    async def create_draft_node(state: AccountOpeningState) -> dict[str, Any]:
        return await create_draft(state, draft_api)

    workflow.add_node("create_draft", create_draft_node)

    workflow.add_edge(START, "understand_request")
    workflow.add_conditional_edges("understand_request", route_after_setup, {"show_setup": "prepare_account_setup", "retrieve_client": "retrieve_client"})
    workflow.add_edge("prepare_account_setup", END)
    workflow.add_edge("retrieve_client", "determine_requirements")
    workflow.add_edge("determine_requirements", "prepare_ui")
    workflow.add_conditional_edges(
        "prepare_ui", route_after_requirements,
        {"wait_for_input": END, "await_approval": "await_approval"},
    )
    workflow.add_conditional_edges(
        "await_approval", route_after_approval,
        {"create_draft": "create_draft", "revalidate": "retrieve_client", "finish": END},
    )
    workflow.add_edge("create_draft", END)
    saver = checkpointer if checkpointer_override is None else checkpointer_override
    return workflow.compile(checkpointer=saver)

from __future__ import annotations

import re
import uuid
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
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
    if model is not None and text:
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
    return {
        "client_id": client_id,
        "account_type": account_type.upper(),
        "ownership": ownership.upper(),
        "base_currency": currency.upper(),
        "joint_owner_name": owner or state.get("joint_owner_name", ""),
        "joint_owner_tax_residency": tax or state.get("joint_owner_tax_residency", ""),
    }


def retrieve_client(state: AccountOpeningState) -> dict[str, Any]:
    # Replace with an authenticated call to the Java Client Experience API.
    client_id = state.get("client_id", "C12345")
    return {"client_profile": {
        "clientId": client_id,
        "displayName": "Alex Morgan",
        "segment": "PRIVATE_BANKING",
        "kycStatus": "VALID",
        "riskProfile": "MODERATE",
    }}


def determine_requirements(state: AccountOpeningState) -> dict[str, Any]:
    missing: list[str] = []
    if state.get("ownership") == "JOINT":
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
            "The mock KYC service reports VALID. Please provide the joint owner's name and tax residency."
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
        "joint_owner_tax_residency": r"(?:joint owner )?tax residency\s+(?:to|is)\s+([A-Za-z][A-Za-z .'-]+?)(?:\.|,|;|$)",
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
            "messages": [AIMessage(content="Application review confirmed. Creating the mock draft now.")],
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


def create_mock_draft(state: AccountOpeningState) -> dict[str, Any]:
    if state.get("approval_status") != "APPROVED":
        raise ValueError("Draft creation blocked: explicit application approval is required.")

    draft = {
        "applicationId": f"AO-{uuid.uuid4().hex[:8].upper()}",
        "status": "DRAFT",
        "clientId": state["client_id"],
        "accountType": state["account_type"],
        "ownership": state["ownership"],
        "baseCurrency": state["base_currency"],
        "jointOwner": {
            "name": state.get("joint_owner_name", ""),
            "taxResidency": state.get("joint_owner_tax_residency", ""),
        } if state.get("ownership") == "JOINT" else None,
    }
    return {
        "application": draft,
        "ui": {
            "mode": "COMPLETE",
            "widgetId": "DRAFT_CONFIRMATION",
            "title": "Draft created",
            "description": "A mock account-opening draft was created after explicit confirmation. No real account has been opened.",
            "fields": [],
            "data": {
                "applicationId": draft["applicationId"],
                "status": draft["status"],
                "clientId": draft["clientId"],
            },
        },
        "messages": [AIMessage(content=f"Account-opening draft {draft['applicationId']} was created successfully. No account has been submitted or opened.")],
    }


def route_after_requirements(state: AccountOpeningState) -> str:
    return "wait_for_input" if state.get("missing_fields") else "await_approval"


def route_after_approval(state: AccountOpeningState) -> str:
    if state.get("approval_status") == "APPROVED":
        return "create_draft"
    if state.get("approval_status") == "PENDING" and state.get("review_action") == "EDIT":
        return "revalidate"
    return "finish"


def build_graph():
    workflow = StateGraph(AccountOpeningState)
    workflow.add_node("understand_request", understand_request)
    workflow.add_node("retrieve_client", retrieve_client)
    workflow.add_node("determine_requirements", determine_requirements)
    workflow.add_node("prepare_ui", prepare_ui)
    workflow.add_node("await_approval", await_human_approval)
    workflow.add_node("create_draft", create_mock_draft)

    workflow.add_edge(START, "understand_request")
    workflow.add_edge("understand_request", "retrieve_client")
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
    return workflow.compile(checkpointer=MemorySaver())


graph = build_graph()

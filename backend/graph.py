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
        r"(?:joint owner|co-owner)(?: name)?\s*(?:is|:)\s*([A-Za-z][A-Za-z .'-]+?)(?:,|;|$)",
        text, state.get("joint_owner_name", "")
    )
    tax = extracted.get("joint_owner_tax_residency") or extract_value(
        r"(?:tax residency|residency)\s*(?:is|:)\s*([A-Za-z][A-Za-z .'-]+?)(?:,|;|$)",
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
        return {"ui": ui, "messages": [AIMessage(content=message)]}

    profile = state.get("client_profile", {})
    ui = {
        "mode": "SUMMARY",
        "widgetId": "APPLICATION_SUMMARY",
        "title": "Review application details",
        "description": "Check the details below. The draft will be created only after you explicitly confirm.",
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
        },
        "approvalRequired": True,
    }
    message = "All required POC fields are present. Please review the application and explicitly confirm or reject it."
    return {
        "ui": ui,
        "approval_status": "PENDING",
        "messages": [AIMessage(content=message)],
    }


def await_human_approval(state: AccountOpeningState) -> dict[str, Any]:
    # This node has no side effects before interrupt: LangGraph may re-run it on resume.
    if state.get("approval_status") != "PENDING":
        raise ValueError("There is no pending application review to resume.")

    decision = interrupt({
        "kind": "ACCOUNT_OPENING_APPROVAL",
        "message": "Review the application details and choose Confirm draft or Reject.",
        "application": state.get("ui", {}).get("data", {}),
    })

    approved = (
        isinstance(decision, dict)
        and decision.get("action") == "APPROVE"
        and decision.get("approved") is True
    )
    if approved:
        return {
            "approval_status": "APPROVED",
            "messages": [AIMessage(content="Application review confirmed. Creating the mock draft now.")],
        }

    return {
        "approval_status": "REJECTED",
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
    # Defense in depth: never create a draft unless the graph recorded approval.
    if state.get("approval_status") != "APPROVED":
        raise ValueError("Draft creation blocked: explicit application approval is required.")

    # Replace with POST /account-applications/drafts in the Java Experience API.
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
    return "create_draft" if state.get("approval_status") == "APPROVED" else "finish"


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
        {"create_draft": "create_draft", "finish": END},
    )
    workflow.add_edge("create_draft", END)
    return workflow.compile(checkpointer=MemorySaver())


graph = build_graph()

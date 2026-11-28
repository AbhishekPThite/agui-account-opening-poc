from __future__ import annotations

from typing import Any

from langgraph.graph import StateGraph, START, END
from ..infrastructure.checkpointer import checkpointer
from .state import AccountOpeningState
from .nodes import (
    assess_client_profile,
    await_human_approval,
    create_draft,
    open_dashboard_section,
    prepare_application_dashboard,
    prepare_joint_owner_capture,
    prepare_profile_capture,
    publish_journey_status,
    retrieve_client,
    understand_request,
)

def route_after_request(state: AccountOpeningState) -> str:
    if state.get("conversation_only"):
        return "stay"
    if state.get("dashboard_navigation"):
        return "open_section"
    if state.get("profile_capture_requested"):
        return "capture_profile"
    # A joint registration must collect its required co-owner details
    # immediately after account setup, before returning to the dashboard.
    if (
        state.get("last_form_action") == "ACCOUNT_SETUP"
        and str(state.get("ownership", "")).upper() in {"JOINT", "JOINT_TOD"}
        and not (
            state.get("joint_owner_name")
            and state.get("joint_owner_tax_residency")
        )
    ):
        return "joint_owner"
    if not state.get("client_profile") or state.get("profile_data_submitted"):
        return "retrieve_client"
    return "dashboard"

def route_after_status(state: AccountOpeningState) -> str:
    """Route on explicit workflow intent, never on a presentation widget ID."""
    return "await_approval" if state.get("approval_requested") else "finish"

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
    workflow.add_node("prepare_joint_owner_capture", prepare_joint_owner_capture)
    workflow.add_node("prepare_application_dashboard", prepare_application_dashboard)
    workflow.add_node("open_dashboard_section", open_dashboard_section)
    workflow.add_node("publish_journey_status", publish_journey_status)
    async def retrieve_client_node(state: AccountOpeningState) -> dict[str, Any]:
        return await retrieve_client(state, client_api)

    workflow.add_node("retrieve_client", retrieve_client_node)
    workflow.add_node("assess_client_profile", assess_client_profile)
    workflow.add_node("prepare_profile_capture", prepare_profile_capture)
    workflow.add_node("await_approval", await_human_approval)
    async def create_draft_node(state: AccountOpeningState) -> dict[str, Any]:
        return await create_draft(state, draft_api)

    workflow.add_node("create_draft", create_draft_node)

    workflow.add_edge(START, "understand_request")
    workflow.add_conditional_edges(
        "understand_request",
        route_after_request,
        {
            "retrieve_client": "retrieve_client",
            "dashboard": "prepare_application_dashboard",
            "open_section": "open_dashboard_section",
            "capture_profile": "prepare_profile_capture",
            "joint_owner": "prepare_joint_owner_capture",
            "stay": END,
        },
    )
    workflow.add_edge("prepare_joint_owner_capture", "publish_journey_status")
    workflow.add_edge("retrieve_client", "assess_client_profile")
    workflow.add_edge("assess_client_profile", "prepare_application_dashboard")
    workflow.add_edge("prepare_application_dashboard", END)
    workflow.add_edge("open_dashboard_section", "publish_journey_status")
    workflow.add_edge("prepare_profile_capture", "publish_journey_status")
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

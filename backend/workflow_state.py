"""Typed LangGraph state contract for the account-opening workflow.

Keep workflow state definitions separate from graph topology and node
implementations so domain/workflow contracts can evolve independently.
"""
from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


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

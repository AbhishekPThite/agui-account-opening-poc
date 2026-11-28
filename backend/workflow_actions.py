"""Classification of form submissions and active workflow actions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WorkflowActionContext:
    dashboard_navigation: bool = False
    requested_section: str = ""
    setup_submitted: bool = False
    joint_owner_submission: bool = False
    profile_confirmed: bool = False
    profile_capture: bool = False
    profile_capture_requested: bool = False
    beneficiary_capture: bool = False
    beneficiary_prefill: bool = False
    profile_data_prefill: bool = False
    beneficiary_skip: bool = False
    risk_assessment_submission: bool = False
    risk_assessment_prefill: bool = False
    initial_journey_prefill: bool = False
    product_features_submission: bool = False
    product_features_prefill: bool = False


def classify_workflow_action(
    extracted: dict[str, Any],
    *,
    form_submission: bool,
    active_widget: str,
) -> WorkflowActionContext:
    """Translate transport/form identifiers and active widget into workflow flags.

    This function classifies intent only. It does not validate submitted values
    or mutate LangGraph state.
    """
    form_id = str(extracted.get("formId", "")) if form_submission else ""
    dashboard_navigation = form_id == "DASHBOARD_NAVIGATION"
    return WorkflowActionContext(
        dashboard_navigation=dashboard_navigation,
        requested_section=(
            str(extracted.get("section", "")).strip().upper()
            if dashboard_navigation else ""
        ),
        setup_submitted=form_id == "ACCOUNT_SETUP",
        joint_owner_submission=form_id == "JOINT_OWNER_DETAILS",
        profile_confirmed=form_id == "PROFILE_CONFIRMATION",
        profile_capture=form_id == "PROFILE_DATA_CAPTURE",
        profile_capture_requested=form_id == "PROFILE_CAPTURE_REQUEST",
        beneficiary_capture=form_id == "BENEFICIARY_CAPTURE",
        beneficiary_prefill=not form_submission and active_widget == "BENEFICIARY_CAPTURE",
        profile_data_prefill=not form_submission and active_widget == "PROFILE_DATA_CAPTURE",
        beneficiary_skip=form_id == "BENEFICIARY_SKIP",
        risk_assessment_submission=form_id == "RISK_ASSESSMENT",
        risk_assessment_prefill=(
            not form_submission and active_widget == "RISK_ASSESSMENT_FORM"
        ),
        initial_journey_prefill=not form_submission and not active_widget,
        product_features_submission=form_id == "PRODUCT_FEATURES",
        product_features_prefill=(
            not form_submission and active_widget == "PRODUCT_FEATURES_FORM"
        ),
    )

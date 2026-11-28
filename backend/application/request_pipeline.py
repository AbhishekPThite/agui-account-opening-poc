"""Request classification and deterministic validation pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..domain.validation import (
    validate_joint_owner_submission,
    validate_risk_assessment,
    validate_product_features,
)
from .workflow_actions import WorkflowActionContext, classify_workflow_action
from ..workflow.state import AccountOpeningState


@dataclass(frozen=True)
class ValidatedRequestContext:
    actions: WorkflowActionContext
    risk_assessment: dict[str, Any]
    product_features: dict[str, Any]


def prepare_validated_request(
    state: AccountOpeningState,
    extracted: dict[str, Any],
    *,
    form_submission: bool,
    active_widget: str,
) -> ValidatedRequestContext:
    """Classify the request and validate extracted values before state projection."""
    actions = classify_workflow_action(
        extracted,
        form_submission=form_submission,
        active_widget=active_widget,
    )

    if actions.joint_owner_submission:
        validate_joint_owner_submission(extracted)

    risk_requested = (
        actions.risk_assessment_submission
        or actions.risk_assessment_prefill
        or actions.initial_journey_prefill
    )
    risk_assessment = validate_risk_assessment(
        extracted,
        requested=risk_requested,
        submission=actions.risk_assessment_submission,
    )

    product_type = str(
        extracted.get("account_type") or extracted.get("productType")
        or state.get("product_type") or state.get("account_type") or ""
    ).strip().upper()
    features_requested = (
        actions.product_features_submission
        or actions.product_features_prefill
        or (
            actions.initial_journey_prefill
            and product_type in {"BROKERAGE", "CREDIT_FACILITY"}
        )
    )
    product_features = validate_product_features(
        extracted,
        product_type=product_type,
        requested=features_requested,
        submission=actions.product_features_submission,
    )

    return ValidatedRequestContext(
        actions=actions,
        risk_assessment=risk_assessment,
        product_features=product_features,
    )

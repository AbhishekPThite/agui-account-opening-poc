"""Request extraction orchestration for the account-opening graph.

This module selects the appropriate extraction strategy for the active UI step.
It does not validate or mutate workflow state; those responsibilities remain
with the graph/domain layer.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from requirements_engine import build_product_feature_requirements
from workflow_state import AccountOpeningState


Extractor = Callable[..., Awaitable[dict[str, Any]]]
QuestionAnswerer = Callable[..., Awaitable[str]]


async def extract_request_data(
    text: str,
    state: AccountOpeningState,
    *,
    model_enabled: bool,
    extract_account_request_fn: Extractor,
    extract_risk_assessment_fn: Extractor,
    extract_product_features_fn: Extractor,
    extract_active_form_fields_fn: Extractor,
    answer_journey_question_fn: QuestionAnswerer,
) -> tuple[dict[str, Any], str]:
    """Choose an extractor from the active widget and optionally answer a question."""
    extracted: dict[str, Any] = {}
    assistant_answer = ""
    active_ui = state.get("ui", {})
    active_widget = str(active_ui.get("widgetId", ""))

    if active_widget == "RISK_ASSESSMENT_FORM":
        extracted = await extract_risk_assessment_fn(text) if model_enabled else {}
    elif active_widget == "PRODUCT_FEATURES_FORM":
        active_product = str(state.get("product_type", state.get("account_type", ""))).upper()
        product_schema = build_product_feature_requirements(active_product)
        extracted = await extract_product_features_fn(
            text,
            product_type=active_product,
            field_definitions=product_schema["fields"],
        ) if model_enabled else {}
    elif active_widget in {
        "ACCOUNT_SETUP_FORM", "JOINT_OWNER_FORM", "BENEFICIARY_CAPTURE", "PROFILE_DATA_CAPTURE"
    }:
        extracted = await extract_active_form_fields_fn(
            text,
            widget_title=str(active_ui.get("title", "Account opening")),
            field_definitions=active_ui.get("fields", []),
        ) if model_enabled else {}
    elif active_widget == "PROFILE_ASSESSMENT":
        extracted = {}
    else:
        # Initial journey requests can prefill account, risk and product fields.
        extracted = await extract_account_request_fn(text) if model_enabled else {}
        if model_enabled and not active_widget:
            initial_product = str(
                extracted.get("account_type") or extracted.get("productType")
                or state.get("product_type") or state.get("account_type") or ""
            ).upper()
            initial_risk = await extract_risk_assessment_fn(text)
            extracted.update(initial_risk)
            if initial_product in {"BROKERAGE", "CREDIT_FACILITY"}:
                initial_schema = build_product_feature_requirements(initial_product)
                initial_features = await extract_product_features_fn(
                    text,
                    product_type=initial_product,
                    field_definitions=initial_schema["fields"],
                )
                extracted.update(initial_features)

    if not any(str(value).strip() for value in extracted.values()):
        assistant_answer = await answer_journey_question_fn(
            text,
            widget_title=str(active_ui.get("title", "Account opening")),
            widget_description=str(active_ui.get("description", "")),
            field_definitions=active_ui.get("fields", []),
            product_type=str(state.get("product_type", state.get("account_type", ""))),
        )

    return extracted, assistant_answer

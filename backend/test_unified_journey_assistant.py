import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage, HumanMessage
from graph import understand_request, route_after_setup


class UnifiedJourneyAssistantTests(unittest.TestCase):
    def test_question_about_active_step_returns_answer_without_leaving_step(self):
        state = {
            "messages": [HumanMessage(content="What does this profile confirmation mean?")],
            "ui": {
                "widgetId": "PROFILE_ASSESSMENT",
                "title": "Review client profile",
                "description": "Confirm populated client profile details.",
                "fields": [],
            },
            "profile_confirmed": False,
        }
        with patch(
            "graph.answer_journey_question",
            new=AsyncMock(return_value="Review the populated details and confirm they are accurate."),
        ):
            result = asyncio.run(understand_request(state))

        self.assertTrue(result["conversation_only"])
        self.assertEqual(route_after_setup({**state, **result}), "stay")
        self.assertIsInstance(result["messages"][0], AIMessage)
        self.assertIn("confirm", result["messages"][0].content.lower())

    def test_active_form_message_updates_only_explicit_joint_owner_fields(self):
        state = {
            "messages": [HumanMessage(content="The joint owner's name is Jordan Lee.")],
            "ui": {
                "widgetId": "JOINT_OWNER_FORM",
                "title": "Joint owner details",
                "fields": [
                    {"name": "jointOwnerName", "label": "Joint owner full name", "type": "text", "required": True},
                    {"name": "jointOwnerTaxResidency", "label": "Joint owner tax residency", "type": "text", "required": True},
                ],
            },
            "joint_owner_tax_residency": "Singapore",
        }
        with patch("graph.model", object()), patch(
            "graph.extract_active_form_fields", new=AsyncMock(return_value={"jointOwnerName": "Jordan Lee", "jointOwnerTaxResidency": ""})
        ):
            result = asyncio.run(understand_request(state))

        self.assertEqual(result["joint_owner_name"], "Jordan Lee")
        self.assertEqual(result["joint_owner_tax_residency"], "Singapore")
        self.assertFalse(result["conversation_only"])

    def test_initial_request_prefills_risk_and_brokerage_features(self):
        state = {
            "messages": [HumanMessage(content=(
                "Open brokerage account for client C12345. I am investing for about seven years, "
                "need medium liquidity, and am comfortable with moderate risk. My objectives are "
                "growth and income. Opt in to options, keep the sweep vehicle as BDP, and use FIFO "
                "for tax lots."
            ))],
            "ui": {},
        }
        with patch("graph.model", object()), patch(
            "graph.extract_account_request",
            new=AsyncMock(return_value={"client_id": "C12345", "account_type": "BROKERAGE"}),
        ), patch(
            "graph.extract_risk_assessment",
            new=AsyncMock(return_value={
                "investmentObjectives": "GROWTH, INCOME",
                "investmentTimeHorizon": "5_TO_10_YEARS",
                "liquidityNeeds": "MEDIUM",
                "riskTolerance": "MODERATE",
            }),
        ), patch(
            "graph.extract_product_features",
            new=AsyncMock(return_value={
                "cashSweepVehicle": "BDP",
                "optionsTradingElection": "YES",
                "mutualFundsTaxLotMethod": "FIRST_IN_FIRST_OUT",
                "otherSecuritiesTaxLotMethod": "FIRST_IN_FIRST_OUT",
            }),
        ):
            result = asyncio.run(understand_request(state))

        self.assertEqual(result["risk_assessment"]["investmentTimeHorizon"], "5_TO_10_YEARS")
        self.assertEqual(result["risk_assessment"]["liquidityNeeds"], "MEDIUM")
        self.assertEqual(result["risk_assessment"]["riskTolerance"], "MODERATE")
        self.assertEqual(result["risk_assessment"]["investmentObjectives"], "GROWTH, INCOME")
        self.assertEqual(result["product_features"]["optionsTradingElection"], "YES")
        self.assertEqual(result["product_features"]["cashSweepVehicle"], "BDP")
        self.assertEqual(result["product_features"]["mutualFundsTaxLotMethod"], "FIRST_IN_FIRST_OUT")
        self.assertEqual(result["product_features"]["otherSecuritiesTaxLotMethod"], "FIRST_IN_FIRST_OUT")
        self.assertFalse(result["risk_assessment_completed"])
        self.assertFalse(result["product_features_completed"])

    def test_product_question_does_not_mutate_values_or_complete_step(self):
        state = {
            "messages": [HumanMessage(content="Does this approve the credit facility?")],
            "ui": {
                "widgetId": "PRODUCT_FEATURES_FORM",
                "title": "Credit facility details",
                "description": "Provide requested amount, collateral and purpose.",
                "fields": [],
            },
            "product_type": "CREDIT_FACILITY",
            "product_features": {"requestedCreditLimit": 250000.0},
            "product_features_completed": False,
        }
        with patch("graph.model", object()), patch(
            "graph.extract_product_features", new=AsyncMock(return_value={})
        ), patch(
            "graph.answer_journey_question",
            new=AsyncMock(return_value="No. This form captures a request; it does not approve a facility."),
        ):
            result = asyncio.run(understand_request(state))

        self.assertTrue(result["conversation_only"])
        self.assertEqual(result["product_features"], {"requestedCreditLimit": 250000.0})
        self.assertFalse(result["product_features_completed"])
        self.assertIn("does not approve", result["messages"][0].content)


if __name__ == "__main__":
    unittest.main()

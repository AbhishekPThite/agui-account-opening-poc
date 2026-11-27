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

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from langchain_core.messages import HumanMessage
from workflow.nodes import understand_request
from integrations.llm.model_client import extract_account_request


class ConversationalAccountSetupTests(unittest.TestCase):
    def run_extraction(self, message, extracted, existing_state=None):
        state = dict(existing_state or {})
        state["messages"] = [HumanMessage(content=message)]
        with patch("workflow.nodes.model", object()), patch(
            "workflow.nodes.extract_account_request", new_callable=AsyncMock
        ) as extractor, patch(
            "workflow.nodes.extract_risk_assessment", new_callable=AsyncMock, return_value={}
        ), patch(
            "workflow.nodes.extract_product_features", new_callable=AsyncMock, return_value={}
        ):
            extractor.return_value = extracted
            return asyncio.run(understand_request(state))

    def test_conversation_prefills_account_setup_fields(self):
        result = self.run_extraction(
            "Make this a joint brokerage account with margin and call it Family Portfolio.",
            {
                "account_type": "BROKERAGE",
                "ownership": "JOINT",
                "account_nickname": "Family Portfolio",
                "margin_option": "MARGIN",
            },
        )
        self.assertEqual(result["product_type"], "BROKERAGE")
        self.assertEqual(result["ownership"], "JOINT")
        self.assertEqual(result["account_nickname"], "Family Portfolio")
        self.assertEqual(result["margin_option"], "MARGIN")
        self.assertFalse(result["account_setup_complete"])

    def test_follow_up_changes_only_explicitly_extracted_fields(self):
        result = self.run_extraction(
            "Enable margin for this account.",
            {"margin_option": "MARGIN"},
            {
                "product_type": "BROKERAGE",
                "ownership": "JOINT",
                "account_nickname": "Family Portfolio",
                "margin_option": "NONE",
            },
        )
        self.assertEqual(result["product_type"], "BROKERAGE")
        self.assertEqual(result["ownership"], "JOINT")
        self.assertEqual(result["account_nickname"], "Family Portfolio")
        self.assertEqual(result["margin_option"], "MARGIN")

    def test_account_extractor_rejects_unsupported_margin_enum(self):
        with patch("integrations.llm.model_client.extract_structured_data", new_callable=AsyncMock) as extractor:
            extractor.return_value = {
                "client_id": "",
                "account_type": "",
                "ownership": "",
                "joint_owner_name": "",
                "joint_owner_tax_residency": "",
                "account_nickname": "",
                "margin_option": "SPECIAL_MARGIN",
            }
            result = asyncio.run(extract_account_request("Use a special margin option."))
        self.assertEqual(result["margin_option"], "")

    def test_unsupported_margin_value_does_not_overwrite_current_value(self):
        result = self.run_extraction(
            "Use some unsupported margin option.",
            {"margin_option": "SPECIAL_MARGIN"},
            {"margin_option": "NONE"},
        )
        self.assertEqual(result["margin_option"], "NONE")


if __name__ == "__main__":
    unittest.main()

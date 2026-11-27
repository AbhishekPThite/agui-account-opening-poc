import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from langchain_core.messages import HumanMessage
from graph import understand_request


class ConversationalAccountSetupTests(unittest.TestCase):
    def run_extraction(self, message, extracted, existing_state=None):
        state = dict(existing_state or {})
        state["messages"] = [HumanMessage(content=message)]
        with patch("graph.model", object()), patch(
            "graph.extract_account_request", new_callable=AsyncMock
        ) as extractor:
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

    def test_unsupported_margin_value_does_not_overwrite_current_value(self):
        result = self.run_extraction(
            "Use some unsupported margin option.",
            {"margin_option": "SPECIAL_MARGIN"},
            {"margin_option": "NONE"},
        )
        self.assertEqual(result["margin_option"], "NONE")


if __name__ == "__main__":
    unittest.main()

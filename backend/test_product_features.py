import asyncio
import json
import unittest

from langchain_core.messages import HumanMessage
from graph import understand_request, prepare_product_features
from requirements_engine import build_product_feature_requirements


class ProductFeatureTests(unittest.TestCase):
    def test_brokerage_feature_schema_is_product_specific(self):
        schema = build_product_feature_requirements("BROKERAGE")
        self.assertEqual(schema["productType"], "BROKERAGE")
        self.assertEqual(
            [field["name"] for field in schema["fields"]],
            ["onlineAccess", "eDelivery", "cashSweepOption", "marginInformation", "taxLotMethod", "proxyElection"],
        )

    def test_credit_facility_feature_schema_is_product_specific(self):
        schema = build_product_feature_requirements("CREDIT_FACILITY")
        self.assertEqual(schema["productType"], "CREDIT_FACILITY")
        self.assertEqual(
            [field["name"] for field in schema["fields"]],
            ["requestedCreditLimit", "collateralType", "facilityPurpose"],
        )

    def test_unsupported_product_is_rejected(self):
        with self.assertRaises(ValueError):
            build_product_feature_requirements("INVESTMENT")

    def test_credit_facility_form_renders_only_credit_fields(self):
        result = prepare_product_features({
            "product_type": "CREDIT_FACILITY",
            "product_features": {},
        })
        self.assertEqual(result["ui"]["widgetId"], "PRODUCT_FEATURES_FORM")
        self.assertEqual(
            [field["name"] for field in result["ui"]["fields"]],
            ["requestedCreditLimit", "collateralType", "facilityPurpose"],
        )

    def test_brokerage_submission_is_normalized(self):
        payload = {
            "formId": "PRODUCT_FEATURES",
            "onlineAccess": "Enabled",
            "eDelivery": "Paperless",
            "cashSweepOption": "Option A",
            "marginInformation": "As selected during account setup",
            "taxLotMethod": "FIFO",
            "proxyElection": "Client directed",
        }
        state = {
            "product_type": "BROKERAGE",
            "messages": [HumanMessage(content="POC_FORM_SUBMISSION:" + json.dumps(payload))],
        }
        result = asyncio.run(understand_request(state))
        self.assertEqual(result["product_features"], {
            "onlineAccess": "Enabled",
            "eDelivery": "Paperless",
            "cashSweepOption": "Option A",
            "marginInformation": "As selected during account setup",
            "taxLotMethod": "FIFO",
            "proxyElection": "Client directed",
        })
        self.assertTrue(result["product_features_completed"])

    def test_credit_facility_requires_positive_limit_and_valid_enums(self):
        valid = {
            "formId": "PRODUCT_FEATURES",
            "requestedCreditLimit": "250000",
            "collateralType": "securities",
            "facilityPurpose": "liquidity",
        }
        state = {
            "product_type": "CREDIT_FACILITY",
            "messages": [HumanMessage(content="POC_FORM_SUBMISSION:" + json.dumps(valid))],
        }
        result = asyncio.run(understand_request(state))
        self.assertEqual(result["product_features"]["requestedCreditLimit"], 250000.0)
        self.assertEqual(result["product_features"]["collateralType"], "SECURITIES")

        invalid = {**valid, "requestedCreditLimit": "-10"}
        bad_state = {
            "product_type": "CREDIT_FACILITY",
            "messages": [HumanMessage(content="POC_FORM_SUBMISSION:" + json.dumps(invalid))],
        }
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            asyncio.run(understand_request(bad_state))

    def test_incomplete_product_features_are_rejected(self):
        payload = {"formId": "PRODUCT_FEATURES"}
        state = {
            "product_type": "BROKERAGE",
            "messages": [HumanMessage(content="POC_FORM_SUBMISSION:" + json.dumps(payload))],
        }
        with self.assertRaisesRegex(ValueError, "Product features are incomplete"):
            asyncio.run(understand_request(state))


if __name__ == "__main__":
    unittest.main()

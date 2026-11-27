import asyncio
import json
import unittest

from langchain_core.messages import HumanMessage
from graph import understand_request, prepare_product_features
from requirements_engine import build_product_feature_requirements


class ProductFeatureTests(unittest.TestCase):
    def test_brokerage_feature_schema_uses_screenshot_fields_and_defaults(self):
        schema = build_product_feature_requirements("BROKERAGE")
        self.assertEqual(schema["productType"], "BROKERAGE")
        fields = {field["name"]: field for field in schema["fields"]}
        self.assertEqual(
            list(fields),
            ["cashSweepVehicle", "linkedBankingAccount", "optionsTradingElection", "mutualFundsTaxLotMethod", "otherSecuritiesTaxLotMethod"],
        )
        self.assertEqual(fields["cashSweepVehicle"]["defaultValue"], "BDP")
        self.assertEqual(fields["optionsTradingElection"]["defaultValue"], "NO")
        self.assertEqual(fields["mutualFundsTaxLotMethod"]["defaultValue"], "FIRST_IN_FIRST_OUT")
        self.assertEqual(fields["otherSecuritiesTaxLotMethod"]["defaultValue"], "FIRST_IN_FIRST_OUT")
        self.assertNotIn("defaultValue", fields["linkedBankingAccount"])

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
            "cashSweepVehicle": "BDP",
            "optionsTradingElection": "NO",
            "mutualFundsTaxLotMethod": "FIRST_IN_FIRST_OUT",
            "otherSecuritiesTaxLotMethod": "FIRST_IN_FIRST_OUT",
        }
        state = {
            "product_type": "BROKERAGE",
            "messages": [HumanMessage(content="POC_FORM_SUBMISSION:" + json.dumps(payload))],
        }
        result = asyncio.run(understand_request(state))
        self.assertEqual(result["product_features"], {
            "cashSweepVehicle": "BDP",
            "optionsTradingElection": "NO",
            "mutualFundsTaxLotMethod": "FIRST_IN_FIRST_OUT",
            "otherSecuritiesTaxLotMethod": "FIRST_IN_FIRST_OUT",
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

    def test_brokerage_feature_fields_are_optional_and_generic(self):
        payload = {"formId": "PRODUCT_FEATURES"}
        state = {
            "product_type": "BROKERAGE",
            "messages": [HumanMessage(content="POC_FORM_SUBMISSION:" + json.dumps(payload))],
        }
        result = asyncio.run(understand_request(state))
        self.assertEqual(result["product_features"], {})
        self.assertTrue(result["product_features_completed"])

    def test_incomplete_credit_facility_features_are_rejected(self):
        payload = {"formId": "PRODUCT_FEATURES", "requestedCreditLimit": "1000"}
        state = {
            "product_type": "CREDIT_FACILITY",
            "messages": [HumanMessage(content="POC_FORM_SUBMISSION:" + json.dumps(payload))],
        }
        with self.assertRaisesRegex(ValueError, "Product features are incomplete"):
            asyncio.run(understand_request(state))


if __name__ == "__main__":
    unittest.main()

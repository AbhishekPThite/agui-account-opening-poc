import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from langchain_core.messages import HumanMessage
from workflow.nodes import understand_request, prepare_risk_assessment


class RiskAssessmentTests(unittest.TestCase):
    def test_client_profile_values_do_not_prefill_risk_assessment(self):
        result = prepare_risk_assessment({
            "client_id": "C12345",
            "client_profile": {
                "riskProfile": "MODERATE",
                "investmentProfile": {
                    "investmentObjectives": ["GROWTH", "INCOME"],
                    "riskTolerance": "MODERATE",
                },
            },
        })
        self.assertEqual(result["ui"]["widgetId"], "RISK_ASSESSMENT_FORM")
        fields = {field["name"]: field for field in result["ui"]["fields"]}
        self.assertEqual(fields["investmentObjectives"]["defaultValue"], "")
        self.assertEqual(fields["riskTolerance"]["defaultValue"], "")
        self.assertEqual(fields["investmentTimeHorizon"]["defaultValue"], "")
        self.assertEqual(fields["liquidityNeeds"]["defaultValue"], "")
        self.assertNotIn("experienceLevel", fields)
        self.assertNotIn("productKnowledge", fields)
        for name in ("investmentTimeHorizon", "liquidityNeeds"):
            self.assertTrue(fields[name]["required"])
            self.assertEqual(fields[name]["defaultValue"], "")

    def test_explicitly_provided_risk_answers_are_prefilled(self):
        result = prepare_risk_assessment({
            "client_profile": {
                "investmentProfile": {
                    "investmentObjectives": ["INCOME"],
                    "riskTolerance": "CONSERVATIVE",
                },
            },
            "risk_assessment": {
                "investmentObjectives": ["GROWTH", "INCOME"],
                "riskTolerance": "MODERATE",
                "investmentTimeHorizon": "5_TO_10_YEARS",
                "liquidityNeeds": "MEDIUM",
            },
        })
        fields = {field["name"]: field for field in result["ui"]["fields"]}
        self.assertEqual(fields["investmentObjectives"]["defaultValue"], "GROWTH, INCOME")
        self.assertEqual(fields["riskTolerance"]["defaultValue"], "MODERATE")
        self.assertEqual(fields["investmentTimeHorizon"]["defaultValue"], "5_TO_10_YEARS")
        self.assertEqual(fields["liquidityNeeds"]["defaultValue"], "MEDIUM")

    def test_backend_rejects_incomplete_risk_assessment(self):
        payload = {"formId": "RISK_ASSESSMENT", "investmentObjectives": "GROWTH"}
        state = {"messages": [HumanMessage(content="POC_FORM_SUBMISSION:" + json.dumps(payload))]}
        with self.assertRaisesRegex(ValueError, "Risk assessment is incomplete"):
            asyncio.run(understand_request(state))

    def test_conversational_prefill_merges_only_extracted_values_without_completing(self):
        state = {
            "messages": [HumanMessage(content="I need the money in about seven years.")],
            "ui": {"widgetId": "RISK_ASSESSMENT_FORM"},
            "risk_assessment": {
                "investmentObjectives": ["GROWTH", "INCOME"],
                "riskTolerance": "MODERATE",
            },
            "risk_assessment_completed": False,
        }
        extracted = {
            "investmentObjectives": "",
            "investmentTimeHorizon": "5_TO_10_YEARS",
            "liquidityNeeds": "",
            "riskTolerance": "",
        }
        with patch("workflow.nodes.extract_risk_assessment", new=AsyncMock(return_value=extracted)):
            result = asyncio.run(understand_request(state))

        self.assertEqual(result["risk_assessment"]["investmentTimeHorizon"], "5_TO_10_YEARS")
        self.assertEqual(result["risk_assessment"]["investmentObjectives"], ["GROWTH", "INCOME"])
        self.assertEqual(result["risk_assessment"]["riskTolerance"], "MODERATE")
        self.assertFalse(result["risk_assessment_completed"])

    def test_backend_normalizes_and_accepts_complete_risk_assessment(self):
        payload = {
            "formId": "RISK_ASSESSMENT",
            "investmentObjectives": "growth, income",
            "riskTolerance": "moderate",
            "investmentTimeHorizon": "5_to_10_years",
            "liquidityNeeds": "medium",
        }
        state = {"messages": [HumanMessage(content="POC_FORM_SUBMISSION:" + json.dumps(payload))]}
        result = asyncio.run(understand_request(state))
        self.assertEqual(result["risk_assessment"]["investmentObjectives"], ["GROWTH", "INCOME"])
        self.assertEqual(result["risk_assessment"]["riskTolerance"], "MODERATE")
        self.assertTrue(result["risk_assessment_completed"])


if __name__ == "__main__":
    unittest.main()

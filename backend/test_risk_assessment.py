import asyncio
import json
import unittest

from langchain_core.messages import HumanMessage
from graph import understand_request, prepare_risk_assessment


class RiskAssessmentTests(unittest.TestCase):
    def test_existing_profile_values_are_prefilled_and_new_fields_are_required(self):
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
        self.assertEqual(fields["investmentObjectives"]["defaultValue"], "GROWTH, INCOME")
        self.assertEqual(fields["riskTolerance"]["defaultValue"], "MODERATE")
        self.assertNotIn("experienceLevel", fields)
        self.assertNotIn("productKnowledge", fields)
        for name in ("investmentTimeHorizon", "liquidityNeeds"):
            self.assertTrue(fields[name]["required"])
            self.assertEqual(fields[name]["defaultValue"], "")

    def test_backend_rejects_incomplete_risk_assessment(self):
        payload = {"formId": "RISK_ASSESSMENT", "investmentObjectives": "GROWTH"}
        state = {"messages": [HumanMessage(content="POC_FORM_SUBMISSION:" + json.dumps(payload))]}
        with self.assertRaisesRegex(ValueError, "Risk assessment is incomplete"):
            asyncio.run(understand_request(state))

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

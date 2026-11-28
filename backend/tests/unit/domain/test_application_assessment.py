import unittest

from domain.assessment import assess_application


class ApplicationAssessmentTests(unittest.TestCase):
    def test_missing_joint_owner_fields_are_reported_for_joint_registration(self):
        result = assess_application({
            "product_type": "BROKERAGE",
            "ownership": "JOINT",
            "account_nickname": "Family Brokerage",
            "profile_assessment": {"actionRequired": []},
            "risk_assessment": {
                "investmentObjectives": ["GROWTH"],
                "investmentTimeHorizon": "5_TO_10_YEARS",
                "liquidityNeeds": "MEDIUM",
                "riskTolerance": "MODERATE",
            },
        })
        self.assertEqual(
            result["missing_fields"]["ACCOUNT_DETAILS"],
            ["jointOwnerName", "jointOwnerTaxResidency"],
        )
        self.assertEqual(result["statuses"]["ACCOUNT_DETAILS"], "ACTION_REQUIRED")

    def test_risk_assessment_is_not_inferred_from_client_profile(self):
        result = assess_application({
            "product_type": "BROKERAGE",
            "ownership": "INDIVIDUAL",
            "client_profile": {
                "investmentProfile": {
                    "investmentObjectives": ["GROWTH"],
                    "riskTolerance": "MODERATE",
                },
            },
            "profile_assessment": {"actionRequired": []},
            "risk_assessment": {},
        })
        self.assertEqual(
            result["missing_fields"]["RISK_PROFILE"],
            [
                "investmentObjectives",
                "investmentTimeHorizon",
                "liquidityNeeds",
                "riskTolerance",
            ],
        )
        self.assertEqual(result["statuses"]["RISK_PROFILE"], "ACTION_REQUIRED")

    def test_credit_facility_required_features_are_reported(self):
        result = assess_application({
            "product_type": "CREDIT_FACILITY",
            "ownership": "INDIVIDUAL",
            "account_nickname": "Liquidity Facility",
            "profile_assessment": {"actionRequired": []},
            "risk_assessment": {
                "investmentObjectives": ["LIQUIDITY"],
                "investmentTimeHorizon": "3_TO_5_YEARS",
                "liquidityNeeds": "HIGH",
                "riskTolerance": "MODERATE",
            },
            "product_features": {},
        })
        self.assertEqual(
            result["missing_fields"]["FEATURES"],
            ["requestedCreditLimit", "collateralType", "facilityPurpose"],
        )
        self.assertEqual(result["statuses"]["FEATURES"], "ACTION_REQUIRED")

    def test_application_record_not_widget_name_marks_draft_complete(self):
        result = assess_application({
            "application": {"applicationId": "APP-123", "status": "DRAFT"},
            "ui": {"widgetId": "ANY_WIDGET"},
            "product_type": "BROKERAGE",
            "ownership": "INDIVIDUAL",
            "account_nickname": "Brokerage 1",
            "profile_assessment": {"actionRequired": []},
            "risk_assessment": {
                "investmentObjectives": ["GROWTH"],
                "investmentTimeHorizon": "5_TO_10_YEARS",
                "liquidityNeeds": "MEDIUM",
                "riskTolerance": "MODERATE",
            },
        })
        self.assertTrue(result["draft_created"])
        self.assertEqual(result["statuses"]["SUMMARY"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()

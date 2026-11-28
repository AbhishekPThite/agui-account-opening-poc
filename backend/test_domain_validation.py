import unittest

from domain_validation import (
    validate_joint_owner_submission,
    validate_product_features,
    validate_risk_assessment,
)


class DomainValidationTests(unittest.TestCase):
    def test_joint_owner_submission_requires_both_fields(self):
        with self.assertRaisesRegex(ValueError, "jointOwnerTaxResidency"):
            validate_joint_owner_submission({"jointOwnerName": "Jordan Lee"})

    def test_joint_owner_submission_accepts_complete_details(self):
        validate_joint_owner_submission({
            "jointOwnerName": "Jordan Lee",
            "jointOwnerTaxResidency": "Singapore",
        })

    def test_risk_prefill_keeps_only_non_empty_explicit_values(self):
        result = validate_risk_assessment(
            {
                "investmentObjectives": "growth, income",
                "investmentTimeHorizon": "5_TO_10_YEARS",
                "liquidityNeeds": "",
                "riskTolerance": "",
            },
            requested=True,
            submission=False,
        )
        self.assertEqual(result, {
            "investmentObjectives": "growth, income",
            "investmentTimeHorizon": "5_TO_10_YEARS",
        })

    def test_risk_submission_normalizes_and_validates_values(self):
        result = validate_risk_assessment(
            {
                "investmentObjectives": "growth, income",
                "investmentTimeHorizon": "5_to_10_years",
                "liquidityNeeds": "medium",
                "riskTolerance": "moderate",
            },
            requested=True,
            submission=True,
        )
        self.assertEqual(result, {
            "investmentObjectives": ["GROWTH", "INCOME"],
            "investmentTimeHorizon": "5_TO_10_YEARS",
            "liquidityNeeds": "MEDIUM",
            "riskTolerance": "MODERATE",
        })

    def test_risk_submission_rejects_invalid_enum(self):
        with self.assertRaisesRegex(ValueError, "riskTolerance"):
            validate_risk_assessment(
                {
                    "investmentObjectives": "GROWTH",
                    "investmentTimeHorizon": "5_TO_10_YEARS",
                    "liquidityNeeds": "MEDIUM",
                    "riskTolerance": "VERY_HIGH",
                },
                requested=True,
                submission=True,
            )

    def test_brokerage_features_accept_only_schema_values(self):
        result = validate_product_features(
            {"optionsTradingElection": "yes", "cashSweepVehicle": "INVALID"},
            product_type="BROKERAGE",
            requested=True,
            submission=False,
        )
        self.assertEqual(result, {"optionsTradingElection": "YES"})

    def test_credit_facility_submission_requires_all_mandatory_fields(self):
        with self.assertRaisesRegex(ValueError, "Product features are incomplete"):
            validate_product_features(
                {"requestedCreditLimit": "250000"},
                product_type="CREDIT_FACILITY",
                requested=True,
                submission=True,
            )

    def test_credit_facility_submission_normalizes_valid_values(self):
        result = validate_product_features(
            {
                "requestedCreditLimit": "250,000",
                "collateralType": "securities",
                "facilityPurpose": "liquidity",
            },
            product_type="CREDIT_FACILITY",
            requested=True,
            submission=True,
        )
        self.assertEqual(result, {
            "requestedCreditLimit": 250000.0,
            "collateralType": "SECURITIES",
            "facilityPurpose": "LIQUIDITY",
        })

    def test_product_validation_is_skipped_when_not_requested(self):
        self.assertEqual(
            validate_product_features(
                {},
                product_type="",
                requested=False,
                submission=False,
            ),
            {},
        )


if __name__ == "__main__":
    unittest.main()

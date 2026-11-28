import unittest

from application.request_pipeline import prepare_validated_request


class RequestPipelineTests(unittest.TestCase):
    def test_joint_owner_submission_is_validated_before_projection(self):
        with self.assertRaisesRegex(ValueError, "Joint-owner details are incomplete"):
            prepare_validated_request(
                {},
                {"formId": "JOINT_OWNER_DETAILS", "jointOwnerName": "Jordan Lee"},
                form_submission=True,
                active_widget="JOINT_OWNER_FORM",
            )

    def test_initial_brokerage_request_does_not_require_complete_risk_or_features(self):
        result = prepare_validated_request(
            {},
            {"account_type": "BROKERAGE", "riskTolerance": "MODERATE"},
            form_submission=False,
            active_widget="",
        )
        self.assertTrue(result.actions.initial_journey_prefill)
        self.assertEqual(result.risk_assessment, {"riskTolerance": "MODERATE"})
        self.assertEqual(result.product_features, {})

    def test_question_on_profile_screen_does_not_trigger_risk_validation(self):
        result = prepare_validated_request(
            {"product_type": "BROKERAGE"},
            {},
            form_submission=False,
            active_widget="PROFILE_ASSESSMENT",
        )
        self.assertFalse(result.actions.initial_journey_prefill)
        self.assertEqual(result.risk_assessment, {})
        self.assertEqual(result.product_features, {})

    def test_risk_form_submission_requires_all_risk_fields(self):
        with self.assertRaisesRegex(ValueError, "Risk assessment is incomplete"):
            prepare_validated_request(
                {},
                {"formId": "RISK_ASSESSMENT", "riskTolerance": "MODERATE"},
                form_submission=True,
                active_widget="RISK_ASSESSMENT_FORM",
            )


if __name__ == "__main__":
    unittest.main()

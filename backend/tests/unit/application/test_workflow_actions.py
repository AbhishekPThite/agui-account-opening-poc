import unittest

from application.workflow_actions import classify_workflow_action


class WorkflowActionClassificationTests(unittest.TestCase):
    def test_dashboard_navigation_extracts_requested_section(self):
        result = classify_workflow_action(
            {"formId": "DASHBOARD_NAVIGATION", "section": "risk_profile"},
            form_submission=True,
            active_widget="APPLICATION_DASHBOARD",
        )
        self.assertTrue(result.dashboard_navigation)
        self.assertEqual(result.requested_section, "RISK_PROFILE")
        self.assertFalse(result.initial_journey_prefill)

    def test_joint_owner_form_submission_is_classified(self):
        result = classify_workflow_action(
            {"formId": "JOINT_OWNER_DETAILS"},
            form_submission=True,
            active_widget="JOINT_OWNER_FORM",
        )
        self.assertTrue(result.joint_owner_submission)
        self.assertFalse(result.beneficiary_prefill)
        self.assertFalse(result.risk_assessment_submission)

    def test_active_risk_form_message_is_prefill_not_submission(self):
        result = classify_workflow_action(
            {},
            form_submission=False,
            active_widget="RISK_ASSESSMENT_FORM",
        )
        self.assertTrue(result.risk_assessment_prefill)
        self.assertFalse(result.risk_assessment_submission)
        self.assertFalse(result.initial_journey_prefill)

    def test_initial_message_is_initial_journey_prefill(self):
        result = classify_workflow_action(
            {},
            form_submission=False,
            active_widget="",
        )
        self.assertTrue(result.initial_journey_prefill)
        self.assertFalse(result.risk_assessment_submission)
        self.assertFalse(result.product_features_submission)

    def test_form_submission_does_not_also_count_as_conversational_prefill(self):
        result = classify_workflow_action(
            {"formId": "PRODUCT_FEATURES"},
            form_submission=True,
            active_widget="PRODUCT_FEATURES_FORM",
        )
        self.assertTrue(result.product_features_submission)
        self.assertFalse(result.product_features_prefill)

    def test_unknown_form_id_does_not_trigger_known_action(self):
        result = classify_workflow_action(
            {"formId": "UNKNOWN"},
            form_submission=True,
            active_widget="",
        )
        self.assertFalse(result.dashboard_navigation)
        self.assertFalse(result.setup_submitted)
        self.assertFalse(result.profile_confirmed)
        self.assertFalse(result.initial_journey_prefill)


if __name__ == "__main__":
    unittest.main()

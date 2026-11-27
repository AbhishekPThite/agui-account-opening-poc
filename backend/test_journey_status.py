import unittest

from graph import build_journey_status


class JourneyStatusTests(unittest.TestCase):
    def test_profile_action_required_and_joint_owner_action_are_reflected(self):
        result = build_journey_status({
            "ui": {"widgetId": "JOINT_OWNER_FORM"},
            "profile_assessment": {"actionRequired": [{"field": "Personal details|email"}]},
            "account_setup_complete": True,
            "ownership": "JOINT",
            "joint_owner_name": "",
            "joint_owner_tax_residency": "",
        })
        statuses = {stage["id"]: stage["status"] for stage in result["stages"]}
        self.assertEqual(statuses["PROFILE"], "ACTION_REQUIRED")
        self.assertEqual(statuses["ACCOUNT_DETAILS"], "ACTION_REQUIRED")
        self.assertEqual(statuses["RISK_PROFILE"], "PENDING")
        self.assertEqual(result["currentStage"], "ACCOUNT_DETAILS")

    def test_profile_confirmation_required_is_distinct_from_action_required(self):
        result = build_journey_status({
            "ui": {"widgetId": "PROFILE_ASSESSMENT"},
            "profile_assessment": {
                "confirmationRequired": [{"field": "Personal details|email"}],
                "actionRequired": [],
            },
        })
        statuses = {stage["id"]: stage["status"] for stage in result["stages"]}
        self.assertEqual(statuses["PROFILE"], "CONFIRMATION_REQUIRED")
        self.assertEqual(statuses["ACCOUNT_DETAILS"], "PENDING")

    def test_completed_steps_and_current_summary_are_reported(self):
        state = {
            "ui": {"widgetId": "APPLICATION_SUMMARY"},
            "profile_confirmed": True,
            "account_setup_complete": True,
            "ownership": "JOINT",
            "joint_owner_name": "Jordan Morgan",
            "joint_owner_tax_residency": "US",
            "risk_assessment_completed": True,
            "product_features_completed": True,
        }
        result = build_journey_status(state)
        statuses = {stage["id"]: stage["status"] for stage in result["stages"]}
        self.assertEqual(statuses, {
            "PROFILE": "COMPLETED",
            "ACCOUNT_DETAILS": "COMPLETED",
            "RISK_PROFILE": "COMPLETED",
            "FEATURES": "COMPLETED",
            "SUMMARY": "IN_PROGRESS",
        })
        self.assertEqual(result["completedCount"], 4)
        self.assertEqual(result["totalCount"], 5)
        self.assertEqual(result["currentStage"], "SUMMARY")

    def test_draft_confirmation_completes_summary_stage(self):
        result = build_journey_status({
            "ui": {"widgetId": "DRAFT_CONFIRMATION"},
            "profile_confirmed": True,
            "account_setup_complete": True,
            "ownership": "INDIVIDUAL",
            "risk_assessment_completed": True,
            "product_features_completed": True,
        })
        self.assertEqual(result["overallStatus"], "COMPLETED")
        self.assertEqual(result["completedCount"], 5)


if __name__ == "__main__":
    unittest.main()

import unittest

from graph import (build_journey_status, build_application_review_sections, prepare_application_dashboard, open_dashboard_section)


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
        self.assertEqual(statuses["RISK_PROFILE"], "ACTION_REQUIRED")
        self.assertEqual(result["currentStage"], "ACCOUNT_DETAILS")

    def test_populated_profile_is_complete_without_separate_confirmation_click(self):
        result = build_journey_status({
            "ui": {"widgetId": "PROFILE_ASSESSMENT"},
            "profile_assessment": {
                "confirmationRequired": [{"field": "Personal details|email"}],
                "actionRequired": [],
            },
        })
        statuses = {stage["id"]: stage["status"] for stage in result["stages"]}
        self.assertEqual(statuses["PROFILE"], "COMPLETED")
        self.assertEqual(statuses["ACCOUNT_DETAILS"], "ACTION_REQUIRED")

    def test_completed_steps_and_current_summary_are_reported(self):
        state = {
            "ui": {"widgetId": "APPLICATION_SUMMARY"},
            "profile_assessment": {"actionRequired": []},
            "client_profile": {"investmentProfile": {"investmentObjectives": ["GROWTH"], "riskTolerance": "MODERATE"}},
            "product_type": "BROKERAGE",
            "account_type": "BROKERAGE",
            "account_nickname": "Family Brokerage",
            "ownership": "JOINT",
            "joint_owner_name": "Jordan Morgan",
            "joint_owner_tax_residency": "US",
            "risk_assessment": {
                "investmentObjectives": ["GROWTH"],
                "investmentTimeHorizon": "5_TO_10_YEARS",
                "liquidityNeeds": "MEDIUM",
                "riskTolerance": "MODERATE",
            },
            "product_features": {},
        }
        result = build_journey_status(state)
        statuses = {stage["id"]: stage["status"] for stage in result["stages"]}
        self.assertEqual(statuses, {
            "PROFILE": "COMPLETED",
            "ACCOUNT_DETAILS": "COMPLETED",
            "RISK_PROFILE": "COMPLETED",
            "FEATURES": "COMPLETED",
            "SUMMARY": "ACTION_REQUIRED",
        })
        self.assertEqual(result["completedCount"], 4)
        self.assertEqual(result["totalCount"], 5)
        self.assertEqual(result["currentStage"], "SUMMARY")

    def test_dashboard_exposes_section_level_action_statuses(self):
        state = {
            "client_id": "C12345",
            "product_type": "BROKERAGE",
            "ownership": "JOINT",
            "client_profile": {"displayName": "Alex Morgan", "kycStatus": "VALID"},
            "profile_assessment": {
                "confirmationRequired": [{"field": "Personal details|email"}],
                "actionRequired": [],
            },
            "account_nickname": "Brokerage 1",
            "account_setup_complete": False,
            "risk_assessment_completed": False,
            "product_features_completed": False,
            "ui": {},
        }
        result = prepare_application_dashboard(state)
        self.assertEqual(result["ui"]["widgetId"], "APPLICATION_DASHBOARD")
        sections = {item["id"]: item for item in result["ui"]["journeyStatus"]["sections"]}
        self.assertEqual(sections["PROFILE"]["status"], "COMPLETED")
        self.assertEqual(sections["ACCOUNT_DETAILS"]["status"], "ACTION_REQUIRED")
        self.assertEqual(sections["RISK_PROFILE"]["status"], "ACTION_REQUIRED")
        self.assertEqual(sections["FEATURES"]["status"], "COMPLETED")
        self.assertEqual(sections["SUMMARY"]["status"], "PENDING")

    def test_dashboard_section_navigation_opens_requested_section(self):
        state = {
            "requested_section": "RISK_PROFILE",
            "client_id": "C12345",
            "product_type": "BROKERAGE",
            "client_profile": {},
            "risk_assessment": {"riskTolerance": "MODERATE"},
        }
        result = open_dashboard_section(state)
        self.assertEqual(result["ui"]["widgetId"], "RISK_ASSESSMENT_FORM")
        self.assertEqual(
            next(field for field in result["ui"]["fields"] if field["name"] == "riskTolerance")["defaultValue"],
            "MODERATE",
        )

    def test_final_summary_is_blocked_until_required_sections_complete(self):
        state = {
            "requested_section": "SUMMARY",
            "client_id": "C12345",
            "product_type": "BROKERAGE",
            "account_type": "BROKERAGE",
            "ownership": "INDIVIDUAL",
            "client_profile": {"displayName": "Alex Morgan"},
            "profile_assessment": {"confirmationRequired": [], "actionRequired": []},
            "ui": {},
        }
        result = open_dashboard_section(state)
        self.assertEqual(result["ui"]["widgetId"], "APPLICATION_DASHBOARD")
        self.assertFalse(result["ui"].get("approvalRequired", False))
        self.assertIn("not ready for final review", result["messages"][0].content.lower())

    def test_risk_status_does_not_use_values_from_client_profile(self):
        result = build_journey_status({
            "client_profile": {
                "investmentProfile": {
                    "investmentObjectives": ["GROWTH"],
                    "riskTolerance": "MODERATE",
                },
            },
            "product_type": "BROKERAGE",
            "account_nickname": "Brokerage 1",
            "risk_assessment": {},
        })
        statuses = {stage["id"]: stage["status"] for stage in result["stages"]}
        self.assertEqual(statuses["RISK_PROFILE"], "ACTION_REQUIRED")

    def test_final_review_groups_all_sections_for_accordion_display(self):
        sections = build_application_review_sections({
            "client_id": "C12345",
            "client_profile": {
                "clientId": "C12345",
                "displayName": "Alex Morgan",
                "kycStatus": "VALID",
                "investmentProfile": {
                    "investmentObjectives": ["GROWTH"],
                    "riskTolerance": "MODERATE",
                },
            },
            "profile_assessment": {
                "sections": [{
                    "name": "Personal details",
                    "fields": [
                        {"name": "firstName", "label": "First name", "value": "Alex", "required": True, "missing": False},
                        {"name": "email", "label": "Email", "value": "Not provided", "required": True, "missing": True},
                    ],
                }],
            },
            "product_type": "BROKERAGE",
            "account_type": "BROKERAGE",
            "account_nickname": "Brokerage 1",
            "ownership": "INDIVIDUAL",
            "risk_assessment": {
                "investmentObjectives": ["GROWTH"],
                "investmentTimeHorizon": "5_TO_10_YEARS",
                "liquidityNeeds": "MEDIUM",
                "riskTolerance": "MODERATE",
            },
            "beneficiary_data": {},
            "product_features": {},
        })
        by_id = {section["id"]: section for section in sections}
        self.assertEqual(
            set(by_id),
            {"ACCOUNT_DETAILS", "PROFILE", "RISK_PROFILE", "FEATURES"},
        )
        self.assertEqual(by_id["PROFILE"]["status"], "ACTION_REQUIRED")
        self.assertTrue(any(field["missing"] for field in by_id["PROFILE"]["fields"]))
        self.assertEqual(by_id["FEATURES"]["status"], "COMPLETED")

    def test_draft_confirmation_completes_summary_stage(self):
        result = build_journey_status({
            "ui": {"widgetId": "DRAFT_CONFIRMATION"},
            "profile_assessment": {"actionRequired": []},
            "client_profile": {"investmentProfile": {"investmentObjectives": ["GROWTH"], "riskTolerance": "MODERATE"}},
            "product_type": "BROKERAGE",
            "account_type": "BROKERAGE",
            "account_nickname": "Brokerage 1",
            "ownership": "INDIVIDUAL",
            "risk_assessment": {
                "investmentTimeHorizon": "5_TO_10_YEARS",
                "liquidityNeeds": "MEDIUM",
            },
        })
        self.assertEqual(result["overallStatus"], "COMPLETED")
        self.assertEqual(result["completedCount"], 5)


if __name__ == "__main__":
    unittest.main()

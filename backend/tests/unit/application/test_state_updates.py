import unittest

from application.workflow_actions import classify_workflow_action
from application.state_updates import build_state_updates


class StateUpdateProjectionTests(unittest.TestCase):
    def test_profile_capture_merges_values_without_mutating_existing_state(self):
        state = {
            "application_data": {"firstName": "Asha"},
            "confirmed_profile_data": {"firstName": "Asha"},
            "ui": {"widgetId": "PROFILE_DATA_CAPTURE"},
        }
        extracted = {"lastName": "Rao", "city": "Pune"}
        actions = classify_workflow_action(
            extracted, form_submission=False, active_widget="PROFILE_DATA_CAPTURE"
        )

        result = build_state_updates(
            state,
            extracted=extracted,
            text="My last name is Rao and city is Pune",
            actions=actions,
            form_submission=False,
            assistant_answer="",
            submitted_risk={},
            submitted_features={},
        )

        self.assertEqual(result["application_data"], {"firstName": "Asha", "lastName": "Rao", "city": "Pune"})
        self.assertEqual(state["application_data"], {"firstName": "Asha"})
        self.assertFalse(result["profile_data_submitted"])

    def test_conversational_prefill_does_not_mark_assessment_complete(self):
        state = {
            "risk_assessment": {"riskTolerance": "MODERATE"},
            "product_features": {"cashSweepVehicle": "BDP"},
        }
        actions = classify_workflow_action(
            {}, form_submission=False, active_widget="RISK_ASSESSMENT_FORM"
        )

        result = build_state_updates(
            state,
            extracted={},
            text="I am comfortable with moderate risk",
            actions=actions,
            form_submission=False,
            assistant_answer="",
            submitted_risk={"riskTolerance": "MODERATE"},
            submitted_features={},
        )

        self.assertFalse(result["risk_assessment_completed"])
        self.assertEqual(result["risk_assessment"], {"riskTolerance": "MODERATE"})
        self.assertEqual(result["product_features"], {"cashSweepVehicle": "BDP"})

    def test_form_action_identifier_is_preserved_for_any_form(self):
        extracted = {"formId": "PROFILE_DATA_CAPTURE"}
        actions = classify_workflow_action(
            extracted, form_submission=True, active_widget="PROFILE_DATA_CAPTURE"
        )
        result = build_state_updates(
            {},
            extracted=extracted,
            text="POC_FORM_SUBMISSION:{}",
            actions=actions,
            form_submission=True,
            assistant_answer="",
            submitted_risk={},
            submitted_features={},
        )
        self.assertEqual(result["last_form_action"], "PROFILE_DATA_CAPTURE")
        self.assertTrue(result["profile_data_submitted"])

    def test_question_answer_is_returned_as_ai_message_and_stays_conversational(self):
        from langchain_core.messages import AIMessage

        actions = classify_workflow_action(
            {}, form_submission=False, active_widget="PROFILE_ASSESSMENT"
        )
        result = build_state_updates(
            {"ui": {"widgetId": "PROFILE_ASSESSMENT"}},
            extracted={},
            text="What does this mean?",
            actions=actions,
            form_submission=False,
            assistant_answer="Please review the profile details.",
            submitted_risk={},
            submitted_features={},
        )
        self.assertTrue(result["conversation_only"])
        self.assertIsInstance(result["messages"][0], AIMessage)
        self.assertEqual(result["messages"][0].content, "Please review the profile details.")


if __name__ == "__main__":
    unittest.main()

"""Unit tests for account-opening graph routing decisions."""

import unittest

from graph import route_after_request, route_after_status


class RouteAfterRequestTests(unittest.TestCase):
    def test_conversation_only_request_stays_at_end(self):
        self.assertEqual(route_after_request({"conversation_only": True}), "stay")

    def test_dashboard_navigation_opens_requested_section(self):
        self.assertEqual(
            route_after_request({"dashboard_navigation": True}),
            "open_section",
        )

    def test_profile_capture_request_routes_to_profile_capture(self):
        self.assertEqual(
            route_after_request({"profile_capture_requested": True}),
            "capture_profile",
        )

    def test_joint_registration_without_owner_details_routes_to_joint_owner(self):
        state = {
            "last_form_action": "ACCOUNT_SETUP",
            "ownership": "JOINT",
            "joint_owner_name": "",
            "joint_owner_tax_residency": "",
        }
        self.assertEqual(route_after_request(state), "joint_owner")

    def test_missing_client_profile_routes_to_retrieval(self):
        self.assertEqual(
            route_after_request({"account_setup_complete": True}),
            "retrieve_client",
        )

    def test_existing_client_profile_routes_to_dashboard(self):
        state = {
            "client_profile": {"clientId": "C12345"},
            "profile_data_submitted": False,
        }
        self.assertEqual(route_after_request(state), "dashboard")


if __name__ == "__main__":
    unittest.main()


class RouteAfterStatusTests(unittest.TestCase):
    def test_explicit_approval_request_routes_to_human_approval(self):
        state = {"approval_requested": True, "ui": {"widgetId": "ANY_WIDGET"}}
        self.assertEqual(route_after_status(state), "await_approval")

    def test_widget_id_does_not_trigger_approval(self):
        state = {"approval_requested": False, "ui": {"widgetId": "APPLICATION_SUMMARY"}}
        self.assertEqual(route_after_status(state), "finish")

    def test_missing_approval_signal_finishes(self):
        self.assertEqual(route_after_status({"ui": {"widgetId": "APPLICATION_SUMMARY"}}), "finish")

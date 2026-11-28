import unittest

from domain.requirements import build_registration_requirements


class RegistrationRequirementsTests(unittest.TestCase):
    def by_key(self, registration_type: str):
        result = build_registration_requirements(registration_type)
        return {item["key"]: item for item in result["requirements"]}

    def test_primary_owner_profile_confirmation_and_risk_are_mandatory_for_all(self):
        for registration in ("INDIVIDUAL", "INDIVIDUAL_TOD", "JOINT", "JOINT_TOD"):
            with self.subTest(registration=registration):
                requirements = self.by_key(registration)
                for key in ("PRIMARY_OWNER_DETAILS", "CLIENT_PROFILE_CONFIRMATION", "RISK_ASSESSMENT"):
                    self.assertEqual(requirements[key]["status"], "MANDATORY")
                    self.assertTrue(requirements[key]["required"])

    def test_joint_owner_is_required_only_for_joint_registrations(self):
        for registration in ("INDIVIDUAL", "INDIVIDUAL_TOD"):
            with self.subTest(registration=registration):
                item = self.by_key(registration)["JOINT_OWNER_DETAILS"]
                self.assertEqual(item["status"], "NOT_REQUIRED")
                self.assertFalse(item["required"])
        for registration in ("JOINT", "JOINT_TOD"):
            with self.subTest(registration=registration):
                item = self.by_key(registration)["JOINT_OWNER_DETAILS"]
                self.assertEqual(item["status"], "MANDATORY")
                self.assertTrue(item["required"])

    def test_beneficiary_is_optional_for_every_registration(self):
        for registration in ("INDIVIDUAL", "INDIVIDUAL_TOD", "JOINT", "JOINT_TOD"):
            with self.subTest(registration=registration):
                item = self.by_key(registration)["BENEFICIARY_DETAILS"]
                self.assertEqual(item["status"], "OPTIONAL")
                self.assertFalse(item["required"])

    def test_unknown_registration_is_rejected(self):
        with self.assertRaises(ValueError):
            build_registration_requirements("CORPORATE")


if __name__ == "__main__":
    unittest.main()

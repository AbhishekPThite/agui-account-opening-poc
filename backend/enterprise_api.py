from __future__ import annotations

import logging
import os
import uuid
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

MOCK_DRAFTS_BY_KEY: dict[str, dict[str, Any]] = {}

MOCK_CLIENT_PROFILE = {
    "clientId": "C12345",
    "displayName": "Alex Morgan",
    "segment": "PRIVATE_BANKING",
    "kycStatus": "VALID",
    "riskProfile": "MODERATE",
    "personalDetails": {"firstName": "Alex", "lastName": "Morgan", "dateOfBirth": "1982-04-18", "email": "alex.morgan@example.test", "phone": "+1-212-555-0142"},
    "addresses": {"residential": {"line1": "100 Park Avenue", "line2": "Apt 12B", "city": "New York", "state": "NY", "postalCode": "10017", "country": "US"}, "mailingSameAsResidential": True, "mailing": None},
    "taxResidencies": [{"country": "US", "taxIdType": "SSN", "taxIdMasked": "***-**-6789", "status": "DECLARED"}],
    "employment": {"status": "EMPLOYED", "occupation": "Technology Executive", "employerName": "Example Financial Services", "industry": "FINANCIAL_SERVICES"},
    "investmentProfile": {"experienceLevel": "EXPERIENCED", "investmentObjectives": ["GROWTH", "INCOME"], "riskTolerance": "MODERATE", "annualIncomeRange": "250K_500K", "netWorthRange": "1M_5M"}
}


class JavaExperienceApi:
    """Adapter for the hypothetical Java Client and Draft Experience APIs.

    JAVA_API_MODE=mock keeps the POC self-contained.
    JAVA_API_MODE=http enables the configured Java endpoints.
    """

    def __init__(self) -> None:
        self.mode = os.getenv("JAVA_API_MODE", "mock").strip().lower()
        self.base_url = os.getenv("JAVA_API_BASE_URL", "").strip().rstrip("/")
        self.bearer_token = os.getenv("JAVA_API_BEARER_TOKEN", "").strip()
        self.timeout = float(os.getenv("JAVA_API_TIMEOUT_SECONDS", "15"))
        self.ca_cert = os.getenv("JAVA_API_CA_CERT", "").strip()
        self._client: httpx.AsyncClient | None = None

        if self.mode not in {"mock", "http"}:
            raise RuntimeError("JAVA_API_MODE must be either 'mock' or 'http'.")
        if self.mode == "http":
            if not self.base_url:
                raise RuntimeError("JAVA_API_BASE_URL is required when JAVA_API_MODE=http.")
            if not self.bearer_token:
                raise RuntimeError("JAVA_API_BEARER_TOKEN is required when JAVA_API_MODE=http.")

    async def start(self) -> None:
        if self.mode == "mock":
            logger.info("Java Experience API adapter running in MOCK mode.")
            return

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            verify=self.ca_cert if self.ca_cert else True,
            headers={
                "Authorization": f"Bearer {self.bearer_token}",
                "Accept": "application/json",
            },
        )
        logger.info("Java Experience API adapter initialized: %s", self.base_url)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_client_profile(self, client_id: str) -> dict[str, Any]:
        if self.mode == "mock":
            return {**MOCK_CLIENT_PROFILE, "clientId": client_id}

        if self._client is None:
            raise RuntimeError("Java Experience API client has not been started.")

        safe_client_id = quote(client_id, safe="")
        response = await self._client.get(f"/api/v1/clients/{safe_client_id}/profile")
        response.raise_for_status()
        payload = response.json()

        required = ("clientId", "displayName", "segment", "kycStatus", "riskProfile",
                    "personalDetails", "addresses", "taxResidencies", "employment", "investmentProfile")
        missing = [field for field in required if field not in payload]
        if missing:
            raise ValueError("Client Experience API response is missing required sections: " + ", ".join(missing))
        expected_types = {"personalDetails": dict, "addresses": dict, "taxResidencies": list,
                          "employment": dict, "investmentProfile": dict}
        invalid = [field for field, expected in expected_types.items() if not isinstance(payload[field], expected)]
        if invalid:
            raise ValueError("Client Experience API returned invalid profile sections: " + ", ".join(invalid))
        return {field: payload[field] for field in required}

    async def create_draft(
        self,
        application: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Create a draft; repeated keys return the same mock/API result."""
        logger.info("Creating account draft through Java Experience API adapter (mode=%s).", self.mode)
        if self.mode == "mock":
            if idempotency_key not in MOCK_DRAFTS_BY_KEY:
                MOCK_DRAFTS_BY_KEY[idempotency_key] = {
                    "applicationId": f"AO-{uuid.uuid4().hex[:8].upper()}",
                    "status": "DRAFT",
                    "clientId": application["clientId"],
                    "accountType": application["accountType"],
                    "productType": application.get("productType"),
                    "registrationType": application.get("registrationType", application["ownership"]),
                    "accountNickname": application.get("accountNickname"),
                    "marginOption": application.get("marginOption", "NONE"),
                    "ownership": application["ownership"],
                    "jointOwner": application.get("jointOwner"),
                }
            return dict(MOCK_DRAFTS_BY_KEY[idempotency_key])

        if self._client is None:
            raise RuntimeError("Java Experience API client has not been started.")

        response = await self._client.post(
            "/api/v1/account-applications/drafts",
            json=application,
            headers={"Idempotency-Key": idempotency_key},
        )
        response.raise_for_status()
        payload = response.json()
        logger.info("Draft API returned application ID %s.", payload.get("applicationId", "<missing>"))

        required = ("applicationId", "status", "clientId")
        missing = [field for field in required if field not in payload]
        if missing:
            raise ValueError(
                "Draft Application API response is missing required fields: "
                + ", ".join(missing)
            )
        if str(payload["status"]).upper() != "DRAFT":
            raise ValueError(
                "Draft Application API returned an unexpected status: "
                + str(payload["status"])
            )
        if str(payload["clientId"]) != str(application["clientId"]):
            raise ValueError("Draft Application API returned a different client ID.")

        return payload

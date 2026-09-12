"""Verifies the explicit, code-level license-risk tracking for category B
providers (WhoScored, SofaScore) — see DATA_SOURCES.md. These providers must
never be usable without an explicit risk acknowledgement, and the specific
ToS risk they carry must be inspectable as a real attribute, not buried in a
comment that CI can't check."""

import pytest

from app.providers.sofascore.provider import SofaScoreProvider
from app.providers.whoscored.provider import PersonalUseNotAcknowledgedError, WhoScoredProvider

EXPECTED_LICENSE_RISK = "personal_use_only_betting_platform_clause"


@pytest.mark.parametrize("provider_cls", [WhoScoredProvider, SofaScoreProvider])
def test_category_b_provider_carries_explicit_license_risk_flag(provider_cls):
    assert provider_cls.LICENSE_RISK == EXPECTED_LICENSE_RISK


@pytest.mark.parametrize("provider_cls", [WhoScoredProvider, SofaScoreProvider])
def test_category_b_provider_refuses_instantiation_without_acknowledgement(provider_cls):
    with pytest.raises(PersonalUseNotAcknowledgedError):
        provider_cls()


@pytest.mark.parametrize("provider_cls", [WhoScoredProvider, SofaScoreProvider])
def test_category_b_provider_is_never_available(provider_cls):
    provider = provider_cls(acknowledge_personal_use_only=True)
    assert provider.is_available() is False
    with pytest.raises(NotImplementedError):
        provider.get_historical_matches("EPL", "2024/2025")

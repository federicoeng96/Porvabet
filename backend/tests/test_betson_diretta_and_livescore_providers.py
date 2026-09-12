"""Verifies the explicit, code-level override/risk tracking for the two
pre-match-odds sources (Betson via diretta.it, livescore.com) — see
DATA_SOURCES.md. Neither is implemented (both are verified-blocked, not just
unimplemented), but the risk/override machinery around them must be real and
inspectable, same standard as the category B providers.
"""

import pytest

from app.providers.betson_diretta.provider import (
    BETSON_DIRETTA_BOOKMAKER_LABEL,
    BetsonDirettaOddsProvider,
    BetsonTosOverrideNotAcknowledgedError,
)
from app.providers.livescore.provider import LIVESCORE_BOOKMAKER_LABEL, LivescoreOddsProvider

EXPECTED_BETSON_LICENSE_RISK = "explicit_tos_prohibition_no_personal_use_exception_user_override"


def test_betson_diretta_carries_distinct_explicit_override_license_risk_flag():
    # Must differ from the B_PERSONAL_USE_ONLY providers' flag — this is a
    # knowing override of an absolute prohibition, not an ambiguity resolved
    # in the user's favor.
    assert BetsonDirettaOddsProvider.LICENSE_RISK == EXPECTED_BETSON_LICENSE_RISK


def test_betson_diretta_refuses_instantiation_without_override_acknowledgement():
    with pytest.raises(BetsonTosOverrideNotAcknowledgedError):
        BetsonDirettaOddsProvider()


def test_betson_diretta_is_never_available_yet():
    provider = BetsonDirettaOddsProvider(acknowledge_user_override=True)
    assert provider.is_available() is False
    assert provider.bookmaker_name == BETSON_DIRETTA_BOOKMAKER_LABEL
    with pytest.raises(NotImplementedError):
        provider.get_odds_for_match("AS Roma", "Inter", "2026-09-12T18:45:00Z")


def test_betson_diretta_never_labeled_as_generic_bookmaker():
    # The brief requires this exact label everywhere, never a generic
    # "bookmaker" string, since diretta.it only displays a third party's
    # licensed price.
    assert "diretta.it" in BETSON_DIRETTA_BOOKMAKER_LABEL
    assert BETSON_DIRETTA_BOOKMAKER_LABEL != "bookmaker"


def test_livescore_is_never_available_yet():
    provider = LivescoreOddsProvider()
    assert provider.is_available() is False
    assert provider.bookmaker_name == LIVESCORE_BOOKMAKER_LABEL
    with pytest.raises(NotImplementedError):
        provider.get_odds_for_match("Atalanta", "Cagliari", "2026-09-12T18:45:00Z")

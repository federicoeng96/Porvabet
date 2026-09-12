"""Tests CorriereDelloSportLineupProvider's HTML parsing against a fixture that
mirrors the real markup structure verified live in this session (CSS class
names, HTML-comment-split <time> text, one match with formations not yet
announced and one with them populated) — never against the live site in
automated tests, per this project's convention (see test_football_data_provider,
test_understat_provider for the same pattern of a synthetic fixture with a
real schema).
"""

import httpx

from app.models.enums import DataSourceCategory
from app.providers.corriere_dello_sport.provider import CorriereDelloSportLineupProvider

# Trimmed but structurally faithful to the real page fetched live from
# https://www.corrieredellosport.it/probabili-formazioni/calcio/serie-a in
# this session: HTML comments splitting the <time> text, and
# ProbabiliFormazioni_teamName__*/ProbabiliFormazioni_teamFormation__* divs
# per side, empty until the source has announced a formation.
_FIXTURE_HTML = """
<div data-item="item-1" id="1">
<time class="ProbabiliFormazioni_day__LzCUq">sabato<!-- --> <!-- -->12.09.2026<!-- --> ore <!-- -->18:00</time>
<div class="ProbabiliFormazioni_teams__w3MgR">
<div class="ProbabiliFormazioni_home__jvf4E"><div><div class="ProbabiliFormazioni_teamName__uaRrh">Lazio</div><div class="ProbabiliFormazioni_teamFormation__vdTlT"></div></div></div>
<div class="ProbabiliFormazioni_away__hkEKA"><div><div class="ProbabiliFormazioni_teamName__uaRrh">Milan</div><div class="ProbabiliFormazioni_teamFormation__vdTlT"></div></div></div>
</div>
</div>
<div data-item="item-2" id="2">
<time class="ProbabiliFormazioni_day__LzCUq">sabato<!-- --> <!-- -->12.09.2026<!-- --> ore <!-- -->20:45</time>
<div class="ProbabiliFormazioni_teams__w3MgR">
<div class="ProbabiliFormazioni_home__jvf4E"><div><div class="ProbabiliFormazioni_teamName__uaRrh">Atalanta</div><div class="ProbabiliFormazioni_teamFormation__vdTlT">3-4-3</div></div></div>
<div class="ProbabiliFormazioni_away__hkEKA"><div><div class="ProbabiliFormazioni_teamName__uaRrh">Cagliari</div><div class="ProbabiliFormazioni_teamFormation__vdTlT">4-4-2</div></div></div>
</div>
</div>
"""


def _mock_client() -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_FIXTURE_HTML)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_is_category_b_and_available():
    provider = CorriereDelloSportLineupProvider(http_client=_mock_client())
    assert provider.category == DataSourceCategory.B_PERSONAL_USE_ONLY
    assert provider.is_official_source is False
    assert provider.is_available() is True


def test_returns_nothing_when_formation_not_yet_announced():
    provider = CorriereDelloSportLineupProvider(http_client=_mock_client())
    records = provider.get_probable_lineups("Lazio", "Milan", "2026-09-12T16:00:00Z")
    assert records == []  # never a placeholder/guess when the source has nothing yet


def test_returns_formation_once_announced():
    provider = CorriereDelloSportLineupProvider(http_client=_mock_client())
    records = provider.get_probable_lineups("Atalanta", "Cagliari", "2026-09-12T18:45:00Z")

    assert {r.team_name for r in records} == {"Atalanta", "Cagliari"}
    by_team = {r.team_name: r for r in records}
    assert by_team["Atalanta"].formation == "3-4-3"
    assert by_team["Cagliari"].formation == "4-4-2"
    for r in records:
        # Explicit, documented limitation: this source is formation-only.
        assert r.player_names_starting == []
        assert r.is_official is False
        assert r.source_key == "corriere_dello_sport"


def test_returns_nothing_for_unknown_fixture():
    provider = CorriereDelloSportLineupProvider(http_client=_mock_client())
    records = provider.get_probable_lineups("Roma", "Juventus", "2026-09-12T18:45:00Z")
    assert records == []

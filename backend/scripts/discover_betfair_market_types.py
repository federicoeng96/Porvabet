#!/usr/bin/env python3
"""Discover the REAL Betfair Exchange market types available for the
upcoming fixtures already in the DB (`Match.status == SCHEDULED`) — the
concrete next step for confirming whether Betfair really lists corner/card
markets for these fixtures, and if so, exactly what their market type code
and runner names look like.

**Why this script exists.** This project's Betfair provider only implements
`MATCH_ODDS`/`OVER_UNDER_25` today — every real Betfair documentation source
that would give the exact corners/cards market type code and runner-naming
convention (docs.developer.betfair.com, developer.betfair.com,
support.betfair.com) is blocked by Cloudflare from the sandbox this project
was built in, so guessing that code was deliberately avoided (see
DATA_SOURCES.md, app/providers/betfair/provider.py module docstring). Run
this script from your own machine (where Betfair is NOT blocked) to get the
real answer: it calls Betfair's own `listMarketTypes` for each fixture and
prints every market type Betfair actually has, flagging any that look
corner/card/booking-related.

Usage:
    python scripts/discover_betfair_market_types.py

Requires BETFAIR_APP_KEY/BETFAIR_USERNAME/BETFAIR_PASSWORD already
configured (see RUNNING_LOCALLY.md) and at least one SCHEDULED fixture in
the DB (run scripts/ingest_upcoming_fixtures.py first if the table is
empty).

Never fabricates a result: a fixture Betfair has no market for at all is
reported as "not found on Betfair yet", never a guessed market list.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.models.enums import MatchStatus
from app.models.match import Match
from app.providers.betfair.provider import BetfairExchangeOddsProvider


def main() -> None:
    provider = BetfairExchangeOddsProvider()
    if not provider.is_available():
        print(
            "BETFAIR_APP_KEY/BETFAIR_USERNAME/BETFAIR_PASSWORD not configured — nothing to "
            "do. See RUNNING_LOCALLY.md for how to obtain a free Delayed Application Key."
        )
        return

    db = SessionLocal()
    try:
        matches = db.query(Match).filter(Match.status == MatchStatus.SCHEDULED).all()
        if not matches:
            print(
                "No SCHEDULED fixtures in the DB — run "
                "scripts/ingest_upcoming_fixtures.py first."
            )
            return

        for match in matches:
            home, away = match.home_team.name, match.away_team.name
            print(f"\n=== {home} - {away} ({match.kickoff_utc.isoformat()}) ===")
            try:
                discovered = provider.discover_market_types_for_match(
                    home, away, match.kickoff_utc.isoformat()
                )
            except Exception as exc:  # noqa: BLE001 — report and move to the next fixture
                print(f"  [ERRORE] {exc}")
                continue

            if not discovered:
                print("  Non trovato su Betfair (nessun mercato MATCH_ODDS per questa "
                      "fixture al momento — normale se troppo lontana dal kickoff).")
                continue

            for entry in sorted(discovered, key=lambda d: d.market_type_code):
                flag = "  <-- possibile corner/cartellini" if entry.looks_like_corners_or_cards else ""
                print(f"  {entry.market_type_code:35s} (mercati: {entry.market_count}){flag}")

        print(
            "\nSe hai visto sopra righe marcate 'possibile corner/cartellini', segnalale "
            "(il market_type_code esatto) così il supporto può essere collegato con la "
            "stessa verifica già fatta per MATCH_ODDS/OVER_UNDER_25."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()

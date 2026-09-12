"""Qualitative hypotheses about a team — the input type for the Intelligence
Engine (ROADMAP.md item 6).

**Scope of this first slice, stated plainly**: this module defines the shape
of a qualitative claim; `validation.py` checks one such claim against
observable `TacticalFeature` data (real xG/PPDA/deep-completions from
understat — see ROADMAP.md item 5). Neither module *generates* signals: there
is no news feed, no LLM analysis pipeline, no manual-entry UI wired in yet
that would actually produce an `IntelligenceSignal` from real events — building
one of those is a separate, larger decision (which source, how to phrase a
claim as structured data) not made in this slice. `IntelligenceSignal` is
deliberately a plain in-memory dataclass, not a persisted DB model, for the
same reason: persisting a shape that hasn't been exercised by a real producer
yet would be schema design by guesswork.
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum


class SignalCategory(str, Enum):
    # Only one category has a validation path today (validate_tactical_shift_signal
    # in validation.py) — coaching changes / news events are listed in ROADMAP.md
    # as intended categories but have no observable-data check implemented yet,
    # so they are deliberately not enumerated here until one exists.
    TACTICAL_SHIFT = "TACTICAL_SHIFT"


@dataclass(frozen=True)
class IntelligenceSignal:
    """One qualitative hypothesis about a team, asserted by some external
    source, to be checked against observable data before it can influence
    anything downstream — it is never itself a probability or a risk factor."""

    team_name: str
    category: SignalCategory
    claim: str  # free-text description, for humans/audit trail — never parsed
    asserted_at: date  # the date the claim is said to hold from
    source: str  # who/what asserted it, e.g. "manual", "llm:<model>", "rss:<feed>"

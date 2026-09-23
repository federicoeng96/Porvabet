import enum


class DataSourceCategory(str, enum.Enum):
    """Legal/technical usability category for a data source, per DATA_SOURCES.md.

    A/B/C classify *scraped* sources by ToS risk. `D_OFFICIAL_API_PERSONAL_ACCOUNT`
    is a different kind of thing entirely: an official, documented API accessed
    through the user's own account (e.g. Betfair Exchange's Betting API) — there
    is no scraping/ToS-interpretation risk to classify, the access itself is
    legitimate by design. Never assign this to a source that is actually being
    scraped just to avoid the A/B/C risk conversation.

    `E_COMMERCIAL_AGGREGATOR_API` is different again from D: D is the
    *original* source itself, accessed via the user's own account with that
    source (Betfair is Betfair). E is a third-party commercial product that
    resells/re-aggregates OTHER sources' data as its own paid API business
    (e.g. The Odds API relaying Betfair Exchange + other bookmakers) — under
    its own commercial ToS, which explicitly permits this project's exact use
    case (personal analytical use, displaying in a UI, training statistical
    models) and only prohibits reselling the raw data itself as a standalone
    product. Not scraping (no ToS-interpretation risk like A/B/C), but also
    not "the source itself" (unlike D) — hence its own category. See
    DATA_SOURCES.md "Categoria E".
    """

    A_UNRESTRICTED = "A_UNRESTRICTED"
    B_PERSONAL_USE_ONLY = "B_PERSONAL_USE_ONLY"
    C_ABSTRACT_ONLY = "C_ABSTRACT_ONLY"
    D_OFFICIAL_API_PERSONAL_ACCOUNT = "D_OFFICIAL_API_PERSONAL_ACCOUNT"
    E_COMMERCIAL_AGGREGATOR_API = "E_COMMERCIAL_AGGREGATOR_API"


class MatchStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    LINEUPS_OUT = "LINEUPS_OUT"
    IN_PLAY = "IN_PLAY"
    FINISHED = "FINISHED"
    POSTPONED = "POSTPONED"
    CANCELLED = "CANCELLED"


class MarketCategory(str, enum.Enum):
    MATCH_RESULT = "MATCH_RESULT"          # 1X2
    DOUBLE_CHANCE = "DOUBLE_CHANCE"
    HANDICAP = "HANDICAP"
    TOTAL_GOALS = "TOTAL_GOALS"            # Over/Under
    BOTH_TEAMS_TO_SCORE = "BOTH_TEAMS_TO_SCORE"
    CORNERS = "CORNERS"
    CARDS = "CARDS"
    FOULS = "FOULS"
    PLAYER_SHOTS = "PLAYER_SHOTS"
    PLAYER_SHOTS_ON_TARGET = "PLAYER_SHOTS_ON_TARGET"
    PLAYER_GOALS = "PLAYER_GOALS"
    PLAYER_ASSISTS = "PLAYER_ASSISTS"
    PLAYER_CARDS = "PLAYER_CARDS"
    PLAYER_FOULS = "PLAYER_FOULS"
    PLAYER_PASSES = "PLAYER_PASSES"


class LineupConfidence(str, enum.Enum):
    """Confidence in a pre-match lineup projection."""

    OFFICIAL = "OFFICIAL"                  # published by the club/competition
    PROBABLE_CONFIRMED = "PROBABLE_CONFIRMED"   # SOS Fanta and Gazzetta agree
    PROBABLE_CONFLICTING = "PROBABLE_CONFLICTING"  # sources disagree
    UNKNOWN = "UNKNOWN"


class AlertLevel(str, enum.Enum):
    NONE = "NONE"
    INTERESTING = "INTERESTING"   # 10-15% model/market discrepancy
    STRONG = "STRONG"             # >15%


class ModelFamily(str, enum.Enum):
    DIXON_COLES_POISSON = "DIXON_COLES_POISSON"
    POISSON_COUNT_MODEL = "POISSON_COUNT_MODEL"  # corners/cards attack-defense Poisson, see MODEL_SPEC.md
    NEGATIVE_BINOMIAL = "NEGATIVE_BINOMIAL"
    LOGISTIC_REGRESSION = "LOGISTIC_REGRESSION"
    GRADIENT_BOOSTING = "GRADIENT_BOOSTING"
    BAYESIAN_HIERARCHICAL = "BAYESIAN_HIERARCHICAL"
    PLAYER_PROP_MODEL = "PLAYER_PROP_MODEL"
    ENSEMBLE = "ENSEMBLE"

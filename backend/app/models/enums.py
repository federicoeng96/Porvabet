import enum


class DataSourceCategory(str, enum.Enum):
    """Legal/technical usability category for a data source, per DATA_SOURCES.md."""

    A_UNRESTRICTED = "A_UNRESTRICTED"
    B_PERSONAL_USE_ONLY = "B_PERSONAL_USE_ONLY"
    C_ABSTRACT_ONLY = "C_ABSTRACT_ONLY"


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
    NEGATIVE_BINOMIAL = "NEGATIVE_BINOMIAL"
    LOGISTIC_REGRESSION = "LOGISTIC_REGRESSION"
    GRADIENT_BOOSTING = "GRADIENT_BOOSTING"
    BAYESIAN_HIERARCHICAL = "BAYESIAN_HIERARCHICAL"
    PLAYER_PROP_MODEL = "PLAYER_PROP_MODEL"
    ENSEMBLE = "ENSEMBLE"

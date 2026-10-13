"""Research-only Ben Johnson Special flags based on the nflverse reference spread.

A qualifying game is one where a team coached by Ben Johnson is favored by
0.5 to 3 points. His 2022-2024 Lions offensive-coordinator tenure is included
for historical browsing; his 2025-2026 Bears head-coaching tenure is separate.
No future appointment or sportsbook line is assumed.

nflverse's spread_line is from the home team's perspective:
POSITIVE means HOME favored; NEGATIVE means AWAY favored.
These retrospective/reference lines are not verified live sportsbook quotes.
"""
from __future__ import annotations

import math
import pandas as pd

# Known historical NFL tenures. Do not extrapolate to unconfirmed seasons.
TENURES = {
    2022: ("DET", "Offensive coordinator"),
    2023: ("DET", "Offensive coordinator"),
    2024: ("DET", "Offensive coordinator"),
    2025: ("CHI", "Head coach"),
    2026: ("CHI", "Head coach"),
}

MIN_FAVORITE_POINTS = 0.5
MAX_FAVORITE_POINTS = 3.0


def ben_johnson_special(game: dict) -> dict | None:
    """Return marker only for a known Ben Johnson team favored by 0.5-3 pts."""
    try:
        season = int(game.get("season"))
    except (ValueError, TypeError):
        return None
    tenure = TENURES.get(season)
    if tenure is None or game.get("game_type") != "REG":
        return None
    team, role = tenure
    home, away = str(game.get("home_team")), str(game.get("away_team"))
    if team not in (home, away) or home == away:
        return None

    # Head-coach columns can be blank for games that have not yet kicked off.
    # If an explicit different coach is recorded, fail closed.
    if role == "Head coach":
        coach = game.get("home_coach") if home == team else game.get("away_coach")
        if isinstance(coach, str) and coach.strip() and "ben johnson" not in coach.casefold():
            return None

    try:
        reference_spread = float(game.get("spread_line"))
    except (ValueError, TypeError):
        return None
    if not math.isfinite(reference_spread):
        return None
    favored_by = reference_spread if home == team else -reference_spread
    if not MIN_FAVORITE_POINTS <= favored_by <= MAX_FAVORITE_POINTS:
        return None
    return {
        "team": team,
        "role": role,
        "favored_by": favored_by,
        "source": "nflverse reference spread (not verified live)",
    }


def ben_johnson_flags(schedule: pd.DataFrame, season: int, week: int) -> dict[str, dict]:
    """Map regular-season game IDs to independently qualified research flags."""
    required = {"game_id", "season", "week", "game_type", "home_team",
                "away_team", "spread_line"}
    if schedule is None or schedule.empty or not required.issubset(schedule.columns):
        return {}
    games = schedule[
        schedule["season"].eq(season)
        & schedule["week"].eq(week)
        & schedule["game_type"].eq("REG")
    ]
    markers = {}
    for game in games.to_dict("records"):
        game_id = game.get("game_id")
        if not isinstance(game_id, str) or not game_id.strip() or game_id in markers:
            continue
        marker = ben_johnson_special(game)
        if marker is not None:
            markers[game_id] = marker
    return markers

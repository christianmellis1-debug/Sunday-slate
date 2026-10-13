"""Pregame research-only 'Game to Watch' flags for Sunday Slate.

Reproduces the 0.25 <= Home Field Advantage magnitude < 0.50 research
signal on the *current* weekly nflverse team-stat feed. Separate from the
NFL-ELO-1.0 prediction, Value Research screen, and all betting decisions.

Statistical match only: NO moneyline restriction, because the flag is not
a betting pick. A full betting-screen match would additionally require
verified home-favorite moneyline odds of -100 through -499.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MIN_GAMES = 3
MIN_ELIGIBLE_TEAMS = 16
MIN_MAGNITUDE = 0.25
MAX_MAGNITUDE = 0.50
WEIGHTS = np.array([.40, .25, .15, .10, .10], dtype=float)
STAT_COLUMNS = frozenset({
    "season", "week", "game_id", "season_type", "team", "opponent_team",
    "passing_epa", "rushing_epa", "attempts", "carries", "rushing_yards",
    "completions", "passing_interceptions", "fumbles_lost_total",
    "passing_20", "rushing_10",
})
_NUMERIC = tuple(STAT_COLUMNS - {
    "game_id", "season_type", "team", "opponent_team",
})


def _team_vector(row: dict) -> np.ndarray | None:
    """Totals used by the research test; opponent totals become defensive allowed."""
    totals = np.asarray([
        row["passing_epa"] + row["rushing_epa"],
        row["attempts"] + row["carries"],
        row["rushing_yards"],
        row["carries"],
        row["completions"],
        row["attempts"],
        row["passing_interceptions"] + row["fumbles_lost_total"],
        row["passing_20"] + row["rushing_10"],
        1.0,
    ], dtype=float)
    return totals if np.isfinite(totals).all() and min(totals[1], totals[3], totals[5]) > 0 else None


def _profiles(games: pd.DataFrame, stats: pd.DataFrame, season: int, week: int) -> dict:
    """Compute per-team offensive and defensive z-score ratings from past games only."""
    past = games[
        games["week"].lt(week)
        & games["home_score"].notna()
        & games["away_score"].notna()
    ]
    eligible = stats[
        stats["season"].eq(season)
        & stats["week"].lt(week)
        & stats["season_type"].eq("REG")
    ].copy()
    if eligible.empty or eligible.duplicated(["game_id", "team"]).any():
        return {}

    # Fail closed on incomplete weekly team boxes. Never substitute zeros.
    for field in _NUMERIC:
        eligible[field] = pd.to_numeric(eligible[field], errors="coerce")
    eligible = eligible[eligible[list(STAT_COLUMNS)].notna().all(axis=1)]
    indexed = {(r["game_id"], r["team"]): r for r in eligible.to_dict("records")}

    expected: dict[str, int] = {}
    paired: dict[str, list[np.ndarray]] = {}
    for g in past.to_dict("records"):
        home, away = g["home_team"], g["away_team"]
        expected[home] = expected.get(home, 0) + 1
        expected[away] = expected.get(away, 0) + 1
        h = indexed.get((g["game_id"], home))
        a = indexed.get((g["game_id"], away))
        if h is None or a is None:
            continue
        if (str(h["opponent_team"]) != str(away)
            or str(a["opponent_team"]) != str(home)
            or int(h["week"]) != int(g["week"])
            or int(a["week"]) != int(g["week"])):
            continue
        hv, av = _team_vector(h), _team_vector(a)
        if hv is None or av is None:
            continue
        for team, own, opponent in ((home, hv, av), (away, av, hv)):
            if team not in paired:
                paired[team] = [np.zeros(9), np.zeros(9)]
            paired[team][0] += own
            paired[team][1] += opponent

    values = {}
    for team, (own, opp) in paired.items():
        if own[8] < MIN_GAMES or own[8] != expected[team] or opp[8] != own[8]:
            continue
        if min(own[1], own[3], own[5], opp[1], opp[3], opp[5]) <= 0:
            continue
        offense = [own[0] / own[1], own[2] / own[3], own[4] / own[5],
                   own[6] / own[8], own[7] / own[1]]
        defense = [opp[0] / opp[1], opp[2] / opp[3], opp[4] / opp[5],
                   opp[6] / opp[8], opp[7] / opp[1]]
        values[team] = np.asarray([offense, defense], dtype=float)

    if len(values) < MIN_ELIGIBLE_TEAMS:
        return {}
    names = list(values)
    values_array = np.stack([values[t] for t in names])
    oriented = values_array * np.array([[1, 1, 1, -1, 1], [-1, -1, -1, 1, -1]])
    sd = oriented.std(axis=0)
    if not np.isfinite(sd).all() or (sd < 1e-10).any():
        return {}
    z_scores = (oriented - oriented.mean(axis=0)) / sd
    strength = np.sum(z_scores * WEIGHTS, axis=2)
    return dict(zip(names, strength))


def game_watch_flags(schedule: pd.DataFrame, team_stats: pd.DataFrame,
                     season: int, week: int) -> dict[str, dict]:
    """Map game IDs to research-only Home Field Advantage watch markers.

    No market-price dependency. Prior-week only, season-local, regular-season
    games, full earlier-game coverage, and non-neutral known home venue.
    """
    required_games = {
        "game_id", "season", "week", "game_type", "home_team", "away_team",
        "home_score", "away_score", "location",
    }
    if (schedule is None or team_stats is None or schedule.empty
        or team_stats.empty or not required_games.issubset(schedule.columns)
        or not STAT_COLUMNS.issubset(team_stats.columns)
        or int(week) < MIN_GAMES + 1):
        return {}

    games = schedule[
        schedule["season"].eq(season) & schedule["game_type"].eq("REG")
    ].copy()
    if games.empty or games["game_id"].isna().any() or games["game_id"].duplicated().any():
        return {}
    ratings = _profiles(games, team_stats, int(season), int(week))
    if not ratings:
        return {}

    result: dict[str, dict] = {}
    slate = games[games["week"].eq(week)]
    for g in slate.to_dict("records"):
        # nflverse 'Home' explicitly distinguishes these from neutral sites.
        if str(g.get("location", "")).strip().casefold() != "home":
            continue
        home, away = g["home_team"], g["away_team"]
        if home not in ratings or away not in ratings:
            continue
        home_off, home_def = ratings[home]
        away_off, away_def = ratings[away]
        offense_edge = float(home_off - away_off)
        defense_edge = float(home_def - away_def)
        magnitude = min(offense_edge, defense_edge)
        if (offense_edge > 0 and defense_edge > 0
            and MIN_MAGNITUDE <= magnitude < MAX_MAGNITUDE):
            result[str(g["game_id"])] = {
                "team": str(home),
                "magnitude": round(magnitude, 4),
                "offense_edge": round(offense_edge, 4),
                "defense_edge": round(defense_edge, 4),
            }
    return result

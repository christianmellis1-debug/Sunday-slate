"""Pregame NFL matchup notes from prior completed weekly team/player boxes.

These research metrics do not change the validated Elo pick until a separate
chronological backtest proves an enhancement. No guessed starter/injury status.
"""
from __future__ import annotations

import math
import pandas as pd


def _season_history(frame: pd.DataFrame | None, season: int, week: int) -> pd.DataFrame:
    if frame is None or frame.empty or not {"season", "week", "team"}.issubset(frame.columns):
        return pd.DataFrame()
    work = frame.copy()
    work["season"] = pd.to_numeric(work["season"], errors="coerce")
    work["week"] = pd.to_numeric(work["week"], errors="coerce")
    work = work[work["season"].eq(season) & work["week"].lt(week)]
    if "season_type" in work:
        work = work[work["season_type"].eq("REG")]
    return work


def _number(data: pd.DataFrame, column: str) -> float | None:
    if column not in data or data.empty:
        return None
    values = pd.to_numeric(data[column], errors="coerce")
    return float(values.sum()) if len(values) == int(values.notna().sum()) else None


def _rate(data: pd.DataFrame, numerator: str, denominator: str) -> float | None:
    total = _number(data, numerator)
    attempts = _number(data, denominator)
    if total is None or attempts is None or attempts <= 0:
        return None
    return total / attempts


def _round(value: float | None, digits: int = 3) -> float | None:
    return round(value, digits) if value is not None and math.isfinite(value) else None


def _rows_for_team(frame: pd.DataFrame, team: str) -> pd.DataFrame:
    return frame[frame["team"].astype(str).eq(team)]


def team_advanced_profiles(frame: pd.DataFrame | None, season: int, week: int) -> dict[str, dict]:
    """Passing/rushing EPA per attempt and opponent passing EPA allowed.

    EPA allowed is calculated using each prior opponent's same-game offense,
    never from a season-end defensive summary. This is a proxy, not a complete
    dropback EPA model; attempts can differ from dropbacks.
    """
    work = _season_history(frame, season, week)
    if work.empty:
        return {}
    if "game_id" in work:
        work = work.drop_duplicates(subset=["game_id", "team"], keep=False)
    out = {}
    for team, group in work.groupby("team"):
        key = str(team)
        profile = {
            "games": len(group),
            "pass_epa_per_att": _round(_rate(group, "passing_epa", "attempts")),
            "rush_epa_per_carry": _round(_rate(group, "rushing_epa", "carries")),
            "pass_cpoe": None,
            "pass_epa_allowed_per_att": None,
            "rush_epa_allowed_per_carry": None,
        }
        if "passing_cpoe" in group and "attempts" in group:
            rates = pd.to_numeric(group["passing_cpoe"], errors="coerce")
            weights = pd.to_numeric(group["attempts"], errors="coerce")
            valid = rates.notna() & weights.notna() & weights.gt(0)
            profile["pass_cpoe"] = _round(float((rates[valid] * weights[valid]).sum() / weights[valid].sum()), 2) if valid.any() else None
        out[key] = profile

    if {"game_id", "opponent_team"}.issubset(work.columns):
        # Match a team's offense to the opponent's defense by game, not by the opponent's season mean.
        own = work[["game_id", "team", "opponent_team"]].copy()
        other_cols = [c for c in ("game_id", "team", "opponent_team", "passing_epa", "attempts", "rushing_epa", "carries") if c in work.columns]
        opponent = work[other_cols].copy()
        merged = own.merge(opponent, left_on=["game_id", "team", "opponent_team"],
                           right_on=["game_id", "opponent_team", "team"], how="inner", suffixes=("_own", "_opp"))
        # Join the opponent's own game lines as defensive allowed.
        for team, group in merged.groupby("team_own"):
            key = str(team)
            if key in out:
                out[key]["pass_epa_allowed_per_att"] = _round(_rate(group, "passing_epa", "attempts"))
                out[key]["rush_epa_allowed_per_carry"] = _round(_rate(group, "rushing_epa", "carries"))
    return out


def qb_recent_profiles(frame: pd.DataFrame | None, season: int, week: int) -> dict[str, dict]:
    """Most-used recent passer per team, NOT a confirmed upcoming starter."""
    work = _season_history(frame, season, week)
    if work.empty or not {"position", "player_display_name", "attempts"}.issubset(work):
        return {}
    work = work[work["position"].eq("QB")].copy()
    if work.empty:
        return {}
    work = work[work["week"] >= max(1, week - 4)]
    work["attempts"] = pd.to_numeric(work["attempts"], errors="coerce")
    work = work[work["attempts"].ge(1)]
    group_keys = ["team", "player_display_name"]
    results = {}
    for team, players in work.groupby("team"):
        aggregates = players.groupby(group_keys, dropna=True)["attempts"].sum().sort_values(ascending=False)
        if aggregates.empty:
            continue
        name = str(aggregates.index[0][1])
        recent = players[players["player_display_name"].eq(name)]
        passing = _number(recent, "passing_yards")
        attempts = _number(recent, "attempts")
        intercepts = _number(recent, "passing_interceptions")
        results[str(team)] = {
            "name": name, "last_week": int(recent["week"].max()),
            "attempts": int(attempts) if attempts is not None else None,
            "yards_per_attempt": _round(passing / attempts, 2) if attempts and passing is not None else None,
            "interceptions": int(intercepts) if intercepts is not None else None,
            "label": "Most-used passer, last 4 completed weeks; not a confirmed starter",
        }
    return results


def matchup_research(home: str, away: str, team_profiles: dict, qb_profiles: dict) -> dict:
    return {
        "home": team_profiles.get(home, {}),
        "away": team_profiles.get(away, {}),
        "home_qb": qb_profiles.get(home),
        "away_qb": qb_profiles.get(away),
        "description": "Prior completed regular-season weeks only. Higher offensive EPA/attempt is better; lower opponent EPA allowed/attempt is better. All are descriptive, not a model edge.",
    }

"""NFL injury-report research; strictly game-week and pre-kickoff snapshot only.

This module NEVER infers availability from missing reports, and statuses NEVER
enter the win-probability model. A reported player is not automatically ruled out.
"""
from __future__ import annotations

import pandas as pd


VALID_GAME_STATUSES = {"OUT": "Out", "DOUBTFUL": "Doubtful", "QUESTIONABLE": "Questionable"}


def reported_injuries(data: pd.DataFrame | None, season: int, week: int,
                      kickoff: object, teams: tuple[str, str]) -> dict[str, list[dict]]:
    """Get latest source-dated game-week report status available before kickoff.

    Requires real status, source modification timestamp, and same upcoming game
    week. Never reports players as healthy when missing data. In historical weeks
    it is descriptive; time ordering prevents future knowledge leaking backward.
    """
    result = {str(t): [] for t in teams}
    if data is None or data.empty:
        return result
    needed = {"season", "week", "team", "full_name", "report_status", "date_modified"}
    if not needed.issubset(data.columns):
        return result
    target = pd.to_datetime(kickoff, utc=True, errors="coerce")
    if pd.isna(target):
        return result
    src = data.copy()
    src["season"] = pd.to_numeric(src["season"], errors="coerce")
    src["week"] = pd.to_numeric(src["week"], errors="coerce")
    src["modified"] = pd.to_datetime(src["date_modified"], errors="coerce", utc=True)
    src = src[
        src["season"].eq(season) & src["week"].eq(week) &
        src["team"].isin(teams) & src["modified"].notna() &
        src["modified"].le(target) &
        src["modified"].ge(target - pd.Timedelta(days=8))
    ]
    if src.empty:
        return result
    src = src.sort_values("modified").drop_duplicates(["team", "full_name"], keep="last")
    src["status_norm"] = src["report_status"].astype(str).str.strip().str.upper()
    src = src[src["status_norm"].isin(VALID_GAME_STATUSES)]
    for r in src.itertuples(index=False):
        result[str(r.team)].append({
            "name": str(r.full_name),
            "status": VALID_GAME_STATUSES[r.status_norm],
            "updated_utc": str(r.modified),
        })
    for t in result:
        result[t] = sorted(result[t], key=lambda d: ({"Out": 0, "Doubtful": 1, "Questionable": 2}.get(d["status"], 3), d["name"]))
    return result

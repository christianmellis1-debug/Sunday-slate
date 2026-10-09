"""Pure transforms for NFL scheduling and pregame-only team profiles."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

CENTRAL = ZoneInfo("America/Chicago")
EASTERN = ZoneInfo("America/New_York")


def game_kickoff(gameday: object, gametime: object) -> pd.Timestamp:
    """nflverse gametime is Eastern wall time, even for international games."""
    try:
        date_text = str(gameday).split(" ")[0]
        time_text = str(gametime).strip()
        if len(time_text) == 5:
            time_text += ":00"
        value = pd.Timestamp(f"{date_text} {time_text}")
        if pd.isna(value):
            return pd.NaT
        if value.tzinfo is None:
            value = value.tz_localize(EASTERN, ambiguous="NaT", nonexistent="NaT")
        return value.tz_convert(CENTRAL)
    except (ValueError, TypeError, OverflowError):
        return pd.NaT


def with_kickoffs(schedule: pd.DataFrame) -> pd.DataFrame:
    games = schedule.copy()
    games["kickoff_ct"] = [game_kickoff(row.gameday, row.gametime) for row in games.itertuples(index=False)]
    # Results are treated as complete only when both scores are provided.
    games["completed"] = games["home_score"].notna() & games["away_score"].notna()
    return games


def season_options(schedule: pd.DataFrame) -> list[int]:
    values = pd.to_numeric(schedule["season"], errors="coerce").dropna()
    return sorted({int(v) for v in values if 2000 <= v <= 2100}, reverse=True)


def weeks_for(schedule: pd.DataFrame, season: int, game_type: str = "REG") -> list[int]:
    games = schedule[(schedule["season"] == season) & (schedule["game_type"] == game_type)]
    return sorted({int(n) for n in games["week"].dropna() if n > 0})


def default_week(schedule: pd.DataFrame, season: int, now: datetime, game_type: str = "REG") -> int | None:
    """Select the current slate, then the next slate; otherwise the latest one."""
    weeks = weeks_for(schedule, season, game_type)
    if not weeks:
        return None
    games = schedule[(schedule["season"] == season) & (schedule["game_type"] == game_type)].copy()
    if "kickoff_ct" not in games.columns:
        games = with_kickoffs(games)
    now_ct = pd.Timestamp(now).tz_convert(CENTRAL) if pd.Timestamp(now).tzinfo else pd.Timestamp(now, tz=CENTRAL)
    ranges = []
    for week in weeks:
        times = games.loc[games["week"] == week, "kickoff_ct"].dropna()
        if len(times):
            ranges.append((week, times.min(), times.max()))
    for week, first, last in ranges:
        if first <= now_ct <= last + pd.Timedelta(hours=12):
            return week
    for week, first, _ in ranges:
        if first > now_ct:
            return week
    return ranges[-1][0] if ranges else weeks[-1]


def team_profiles(schedule: pd.DataFrame, team_stats: pd.DataFrame, season: int, week: int) -> dict[str, dict]:
    """Use previous completed weeks only; missing values are not imputed as zero."""
    games = schedule[(schedule["season"] == season) & (schedule["game_type"] == "REG") & (schedule["week"] < week)].copy()
    games = games[games["home_score"].notna() & games["away_score"].notna()]
    output: dict[str, dict] = {}
    for g in games.itertuples(index=False):
        for side in ("home", "away"):
            other = "away" if side == "home" else "home"
            team = str(getattr(g, f"{side}_team"))
            pf = float(getattr(g, f"{side}_score"))
            pa = float(getattr(g, f"{other}_score"))
            row = output.setdefault(team, {"games": 0, "wins": 0, "losses": 0, "ties": 0, "points_for": 0., "points_against": 0., "pass_ypg": None, "rush_ypg": None})
            row["games"] += 1
            row["points_for"] += pf
            row["points_against"] += pa
            row["wins" if pf > pa else "losses" if pf < pa else "ties"] += 1
    for p in output.values():
        p["ppg"] = p.pop("points_for") / p["games"]
        p["opp_ppg"] = p.pop("points_against") / p["games"]

    if team_stats is not None and not team_stats.empty:
        stats = team_stats.copy()
        stats["season"] = pd.to_numeric(stats["season"], errors="coerce")
        stats["week"] = pd.to_numeric(stats["week"], errors="coerce")
        stats = stats[(stats["season"] == season) & (stats["week"] < week)]
        if "season_type" in stats:
            stats = stats[stats["season_type"] == "REG"]
        # Fail closed on ambiguous duplicate weekly records.
        dedup_keys = [key for key in ("season", "week", "team") if key in stats]
        stats = stats.drop_duplicates(subset=dedup_keys, keep=False)
        for abbr, group in stats.groupby("team"):
            key = str(abbr)
            if key not in output:
                output[key] = {"games": 0, "wins": 0, "losses": 0, "ties": 0, "ppg": None, "opp_ppg": None, "pass_ypg": None, "rush_ypg": None}
            for field, target in (("passing_yards", "pass_ypg"), ("rushing_yards", "rush_ypg")):
                if field in group:
                    values = pd.to_numeric(group[field], errors="coerce").dropna()
                    if len(values):
                        output[key][target] = float(values.mean())
    return output


def record_label(profile: dict | None) -> str:
    if not profile or not profile.get("games"):
        return "0-0"
    result = f"{profile['wins']}-{profile['losses']}"
    return result + (f"-{profile['ties']}" if profile["ties"] else "")


def time_label(kickoff: object) -> str:
    if pd.isna(kickoff):
        return "Kickoff TBD"
    return kickoff.strftime("%a %b %-d · %-I:%M %p CT")

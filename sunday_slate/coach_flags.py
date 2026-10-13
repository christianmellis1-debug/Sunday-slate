"""Research-only coaching flags, strictly from DraftKings pregame spreads."""
import math
import pandas as pd

BEN = {2022: ("DET", "Offensive coordinator"),
       2023: ("DET", "Offensive coordinator"),
       2024: ("DET", "Offensive coordinator"),
       2025: ("CHI", "Head coach"), 2026: ("CHI", "Head coach")}
SCHOTT = {2025: "DAL", 2026: "DAL"}
STEF = {2020: "CLE", 2021: "CLE", 2022: "CLE",
        2023: "CLE", 2024: "CLE", 2025: "CLE", 2026: "ATL"}

def _qualify(game, dk, team, name, coach, low, high=None, role="Head coach"):
    if not isinstance(dk, dict) or dk.get("source") != "DraftKings":
        return None
    home = str(game.get("home_team"))
    away = str(game.get("away_team"))
    if home == away or team not in (home, away):
        return None
    given_coach = game.get("home_coach") if home == team else game.get("away_coach")
    if isinstance(given_coach, str) and given_coach.strip() and coach.lower() not in given_coach.lower():
        return None
    try:
        hs, aw = float(dk["home_spread"]), float(dk["away_spread"])
    except (TypeError, ValueError, KeyError, OverflowError):
        return None
    if not all(map(math.isfinite, (hs, aw))) or abs(hs + aw) > .001:
        return None
    # A negative DraftKings spread denotes the favorite.
    spread = hs if home == team else aw
    points = -spread
    if points < low or (high is not None and points > high):
        return None
    return {"name": name, "team": team, "role": role, "favored_by": points,
            "source": "DraftKings", "updated_at": dk.get("updated_at")}

def coaching_flags(schedule: pd.DataFrame, season: int, week: int, quotes: dict | None):
    required = {"game_id", "season", "week", "game_type", "home_team", "away_team"}
    if schedule is None or schedule.empty or not required.issubset(schedule) or not quotes:
        return {}
    out = {}
    for g in schedule.to_dict("records"):
        if g.get("season") != season or g.get("week") != week or g.get("game_type") != "REG" or g.get("completed"):
            continue
        gid = str(g.get("game_id"))
        dk = quotes.get(gid)
        if not dk:
            continue
        flags = []
        ben = BEN.get(season)
        if ben:
            t, role = ben
            m = _qualify(g, dk, t, "BEN JOHNSON SPECIAL", "Ben Johnson", .5, 3., role)
            if m: flags.append(m)
        schott = SCHOTT.get(season)
        if schott:
            m = _qualify(g, dk, schott, "SCHOTTENHEIMER FAVORITE", "Brian Schottenheimer", .5)
            if m: flags.append(m)
        stef = STEF.get(season)
        if stef:
            m = _qualify(g, dk, stef, "STEFANSKI MID-RANGE FAVORITE", "Kevin Stefanski", 3.5, 7.)
            if m: flags.append(m)
        if flags:
            out[gid] = flags
    return out

def ben_johnson_flags(schedule: pd.DataFrame, season: int, week: int, dk_quotes=None):
    """Legacy API; no non-DK fallback."""
    flags = coaching_flags(schedule, season, week, dk_quotes)
    return {gid: next(m for m in markers if m["name"] == "BEN JOHNSON SPECIAL")
            for gid, markers in flags.items()
            if any(m["name"] == "BEN JOHNSON SPECIAL" for m in markers)}

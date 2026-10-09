"""NFL market probability and research screening.

Odds in nflverse schedules are REFERENCE moneylines without a per-quote timestamp
or sportsbook guarantee. They are not executable prices. No sportsbook bets
are recommended by this module. Historical prices represent reference/closing
lines, not verified time-stamped in-play opportunities.
"""
from __future__ import annotations

import math
import pandas as pd

SCREEN_EDGE = 0.05
SCREEN_MIN_PROB = 0.60
SCREEN_ODDS_MIN = -300
SCREEN_ODDS_MAX = 200


def valid_american(value: object) -> int | None:
    """Return integer American odds or None for absent/invalid odds."""
    if value is None or isinstance(value, bool):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(n) or n != int(n):
        return None
    integer = int(n)
    return integer if integer <= -100 or integer >= 100 else None


def implied_probability(odds: int) -> float:
    x = valid_american(odds)
    if x is None:
        raise ValueError("Invalid American odds")
    return 100 / (100 + x) if x > 0 else -x / (100 - x)


def profit_per_unit(odds: int) -> float:
    x = valid_american(odds)
    if x is None:
        raise ValueError("Invalid American odds")
    return x / 100 if x > 0 else 100 / -x


def american_text(odds: int | None) -> str:
    x = valid_american(odds)
    return "Unavailable" if x is None else f"{x:+d}"


def analyze_moneyline(home_probability: float, home_odds: object, away_odds: object) -> dict | None:
    """Two-sided, vig-adjusted probabilities; fail closed on bad/partial lines."""
    ho, ao = valid_american(home_odds), valid_american(away_odds)
    if ho is None or ao is None:
        return None
    try:
        p = float(home_probability)
    except (ValueError, TypeError):
        return None
    if not math.isfinite(p) or not 0 < p < 1:
        return None
    hp, ap = implied_probability(ho), implied_probability(ao)
    overround = hp + ap
    if not 1.0 <= overround <= 1.3:
        return None
    vig_free_home = hp / overround
    sides = {
        "home": {"odds": ho, "model": p, "raw_implied": hp, "no_vig": vig_free_home},
        "away": {"odds": ao, "model": 1 - p, "raw_implied": ap, "no_vig": 1 - vig_free_home},
    }
    for side in sides.values():
        side["edge"] = side["model"] - side["no_vig"]
        side["expected_roi"] = side["model"] * profit_per_unit(side["odds"]) - (1 - side["model"])
    return {"sides": sides, "overround": overround}


def screen_side(market: dict | None, *, edge: float = SCREEN_EDGE, min_prob: float = SCREEN_MIN_PROB) -> str | None:
    """Unvalidated exploratory filter, NOT a recommendation, one side per game."""
    if not market:
        return None
    eligible = [
        name for name, s in market["sides"].items()
        if s["model"] >= min_prob and s["edge"] >= edge
        and SCREEN_ODDS_MIN <= s["odds"] <= SCREEN_ODDS_MAX
    ]
    return eligible[0] if len(eligible) == 1 else None


def historical_screen(schedule: pd.DataFrame, predictions: pd.DataFrame, *,
                      edge: float = SCREEN_EDGE, min_prob: float = SCREEN_MIN_PROB,
                      seasons: tuple[int, ...] = (2023, 2024, 2025)) -> pd.DataFrame:
    """Retrospective ONLY. Uses untimestamped reference lines from game schedules.

    Invalid/partial lines and ties are excluded. Missing years remain empty.
    Do not claim this simulates odds actually available to a bettor.
    """
    cols = ["season", "game_id", "side", "team", "american_odds", "edge",
            "model_probability", "profit_units", "result"]
    required = {"game_id", "home_team", "away_team", "home_score", "away_score", "home_moneyline", "away_moneyline"}
    if not required.issubset(schedule) or not {"game_id", "home_probability", "season", "pick_result"}.issubset(predictions):
        return pd.DataFrame(columns=cols)
    fixtures = schedule.drop_duplicates("game_id", keep=False).set_index("game_id", drop=False)
    out = []
    for p in predictions.to_dict("records"):
        season = int(p["season"])
        gid = str(p["game_id"])
        if season not in seasons or gid not in fixtures.index or p["pick_result"] == "Pending":
            continue
        g = fixtures.loc[gid]
        hs, aw = pd.to_numeric(g["home_score"], errors="coerce"), pd.to_numeric(g["away_score"], errors="coerce")
        if pd.isna(hs) or pd.isna(aw) or hs == aw:
            continue
        market = analyze_moneyline(p["home_probability"], g["home_moneyline"], g["away_moneyline"])
        side = screen_side(market, edge=edge, min_prob=min_prob)
        if side is None:
            continue
        s = market["sides"][side]
        won = (hs > aw) if side == "home" else (aw > hs)
        out.append({
            "season": season, "game_id": gid, "side": side,
            "team": g["home_team"] if side == "home" else g["away_team"],
            "american_odds": s["odds"], "edge": s["edge"],
            "model_probability": s["model"],
            "profit_units": profit_per_unit(s["odds"]) if won else -1.,
            "result": "Win" if won else "Loss",
        })
    return pd.DataFrame(out, columns=cols)


def historical_report(screen: pd.DataFrame) -> dict:
    if screen.empty:
        return {"bets": 0, "wins": 0, "losses": 0, "units": 0.0, "roi": None}
    n = len(screen)
    units = float(screen["profit_units"].sum())
    wins = int(screen["result"].eq("Win").sum())
    return {"bets": n, "wins": wins, "losses": n - wins, "units": units, "roi": units / n}

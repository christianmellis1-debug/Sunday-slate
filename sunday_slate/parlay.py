"""Upcoming-game DraftKings moneyline parlay research.

Only pregame, nonfinal games with genuine two-sided DraftKings prices qualify.
Each leg is drawn either from an authenticated pregame shortlist or from the
existing week-frozen Elo forecasts. Neither is calibrated as a betting edge.
"""
from __future__ import annotations

from itertools import combinations
import math

import pandas as pd

from sunday_slate.market import analyze_moneyline, valid_american

CORE_SOURCE = "Archived core picks"
ELO_SOURCE = "All upcoming Elo favorites"
SORT_CHANCE = "Highest modeled win chance"
SORT_VALUE = "Highest estimated value"


def _utc(value):
    try:
        result = pd.to_datetime(value, utc=True, errors="coerce")
        return result if pd.notna(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _probability(value):
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) and 0.0 < result < 1.0 else None


def eligible_legs(
    slate: pd.DataFrame,
    dk_quotes: dict,
    predictions: dict,
    core: list[dict] | None = None,
    *,
    source: str = ELO_SOURCE,
    min_probability: float = 0.60,
    now=None,
) -> list[dict]:
    """Construct at most one moneyline leg per unstarted matchup.

    Missing, one-sided, non-DK and invalid overround quotes fail closed.
    An archived shortlist is never treated as a substitute for current prices.
    """
    if source not in (CORE_SOURCE, ELO_SOURCE):
        raise ValueError("Unknown prediction source")
    if slate is None or slate.empty or not (0.5 <= min_probability <= 1.0):
        return []
    current = _utc(now) if now is not None else pd.Timestamp.now(tz="UTC")
    if current is None:
        return []
    verified_core = {str(p["game_id"]): p for p in (core or [])
                     if isinstance(p, dict) and p.get("game_id") is not None}
    legs, seen = [], set()
    for game in slate.to_dict("records"):
        gid = str(game.get("game_id") or "")
        if not gid or gid in seen:
            continue
        seen.add(gid)
        if game.get("completed") is not False and game.get("completed") != False:
            continue
        kickoff = _utc(game.get("kickoff_ct"))
        if kickoff is None or kickoff <= current:
            continue
        home, away = str(game.get("home_team") or ""), str(game.get("away_team") or "")
        if not home or not away or home == away:
            continue
        quote = dk_quotes.get(gid) or {}
        if quote.get("source") != "DraftKings":
            continue
        if valid_american(quote.get("home_moneyline")) is None or valid_american(quote.get("away_moneyline")) is None:
            continue

        tier = None
        if source == CORE_SOURCE:
            pick = verified_core.get(gid)
            if (not pick or pick.get("home_team") != home or pick.get("away_team") != away
                    or pick.get("team") not in (home, away)):
                continue
            team = str(pick["team"])
            probability = _probability(pick.get("probability"))
            tier = pick.get("tier")
        else:
            pred = predictions.get(gid)
            if pred is None:
                continue
            team = str(pred.get("predicted_winner") or "")
            home_probability = _probability(pred.get("home_probability"))
            if team not in (home, away) or home_probability is None:
                continue
            probability = home_probability if team == home else 1.0 - home_probability
            # Prevent mixing a winner label with the opposite probability.
            if (team == home) != (home_probability >= .5):
                continue

        if probability is None or probability < min_probability or team not in (home, away):
            continue
        home_probability = probability if team == home else 1.0 - probability
        market = analyze_moneyline(
            home_probability, quote.get("home_moneyline"), quote.get("away_moneyline")
        )
        if market is None:
            continue
        side = "home" if team == home else "away"
        priced_side = market["sides"][side]
        odds = priced_side["odds"]
        decimal = 1 + (odds / 100 if odds > 0 else 100 / -odds)
        legs.append({
            "game_id": gid, "team": team,
            "opponent": away if team == home else home,
            "home_team": home, "away_team": away, "kickoff": kickoff,
            "odds": odds, "decimal": decimal, "probability": probability,
            "edge": priced_side["edge"], "tier": tier, "source": source,
        })
    return sorted(legs, key=lambda x: (-x["probability"], x["game_id"]))


def decimal_to_american(decimal: float) -> str:
    """US moneyline rendering; round to the nearest whole quoted price."""
    if not math.isfinite(decimal) or decimal <= 1.0:
        raise ValueError("Combined payout must exceed stake")
    odds = round(100 * (decimal - 1)) if decimal >= 2 else -round(100 / (decimal - 1))
    return f"{odds:+d}"


def find_parlays(
    legs: list[dict], count: int = 2, *, sort_by: str = SORT_CHANCE,
    limit: int = 3,
) -> list[dict]:
    """Rank distinct-game combinations; do NOT imply independent legs are certain."""
    if count not in (2, 3, 4) or sort_by not in (SORT_CHANCE, SORT_VALUE) or limit < 1:
        return []
    results = []
    for chosen in combinations(legs, count):
        if len({l["game_id"] for l in chosen}) != count:
            continue
        joint = math.prod(leg["probability"] for leg in chosen)
        decimal = math.prod(leg["decimal"] for leg in chosen)
        if not (0 < joint < 1 and math.isfinite(decimal) and decimal > 1):
            continue
        break_even = 1 / decimal
        roi = joint * decimal - 1
        results.append({
            "legs": chosen,
            "probability": joint,
            "decimal": decimal,
            "american": decimal_to_american(decimal),
            "break_even": break_even,
            "estimated_roi": roi,
            "profit_10": 10 * (decimal - 1),
            "payout_10": 10 * decimal,
        })
    if sort_by == SORT_VALUE:
        results.sort(key=lambda p: (-p["estimated_roi"], -p["probability"],
                                    tuple(x["game_id"] for x in p["legs"])))
    else:
        results.sort(key=lambda p: (-p["probability"], -p["estimated_roi"],
                                    tuple(x["game_id"] for x in p["legs"])))
    return results[:limit]

"""Frozen, research-qualified Sunday Slate straight-up shortlist.

Actual weekly display is sourced ONLY from the pregame research/snapshots
archive. Historical 2023–25 figures below are fixed, retrospective backtests,
not odds-based bets or prospectively published weekly cards.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pandas as pd

ARCHIVE_DIR = Path(__file__).resolve().parents[1] / "research" / "snapshots"
HISTORICAL = {
    "name": "Strong core: Heavy Favorite, Double Confirmation, stronger Consensus",
    "source": "research/weekly-shortlist; evaluated on reconstructed preweek inputs",
    "seasons": {
        2023: {"wins": 46, "losses": 19},
        2024: {"wins": 50, "losses": 11},
        2025: {"wins": 52, "losses": 15},
        2026: {"wins": 9, "losses": 2, "through_week": 5},
    },
    "by_tier_2023_2025": {
        1: {"wins": 62, "losses": 14},
        2: {"wins": 46, "losses": 14},
        3: {"wins": 40, "losses": 17},
    },
    "addition_2023_2025": {"wins": 12, "losses": 10},
    "addition_2026_week1_to_5": {"wins": 5, "losses": 1},
    "weeks_2023_2025": 54,
    "weeks_at_least_3_2023_2025": 40,
}
LABELS = {1: "Heavy Favorite", 2: "Double Confirmation", 3: "Strong Consensus"}


def _finite(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        x = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return x if math.isfinite(x) else None


def _team_side(rec, home_probability):
    home, away = str(rec.get("home_team", "")), str(rec.get("away_team", ""))
    team = str(rec.get("elo_winner", ""))
    if not home or not away or home == away:
        return None
    if team not in (home, away):
        return None
    expected = home if home_probability >= .5 else away
    if expected != team:
        return None
    return team


def shortlist(snapshot: dict, *, cap: int = 5, addition_cap: int = 2) -> dict:
    """Apply the already-researched, identical waterfall with no game outcomes.

    Addition candidates are NOT promoted to core recommendations. '68% Elo'
    is a research screen only; retrospective extras covered 12–10 in 2023–25.
    """
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("games"), list):
        return {"core": [], "potential": [], "reason": "No verified frozen slate"}
    core, candidates = [], []
    seen = set()
    for record in snapshot["games"]:
        if not isinstance(record, dict):
            continue
        game_id = str(record.get("game_id", ""))
        if not game_id or game_id in seen:
            continue
        seen.add(game_id)
        conf = _finite(record.get("elo_confidence"))
        hp = _finite(record.get("elo_home_probability"))
        other = _finite(record.get("challenger_home_probability"))
        pp = _finite(record.get("ppg_margin"))
        prior = _finite(record.get("prior_games_min"))
        if (conf is None or hp is None or not .5 <= conf <= 1
                or not 0 <= hp <= 1 or abs(max(hp, 1-hp)-conf) > 1e-6):
            continue
        team = _team_side(record, hp)
        if team is None:
            continue
        challenger_agrees = other is not None and 0 <= other <= 1 and (
            (other >= .5) == (hp >= .5))
        ppg_agrees = prior is not None and prior >= 3 and pp is not None and abs(pp) > 1e-9 and (
            (pp > 0) == (hp >= .5))
        tier = 1 if conf >= .75 else (
            2 if conf >= .60 and ppg_agrees and abs(pp) >= 7 else
            3 if conf >= .65 and ppg_agrees and abs(pp) >= 3 and challenger_agrees else None)
        row = {
            "game_id": game_id,
            "home_team": str(record["home_team"]),
            "away_team": str(record["away_team"]),
            "team": team,
            "probability": conf,
            "tier": tier,
            "ppg_margin": pp,
            "ppg_agrees": bool(ppg_agrees),
            "challenger_agrees": bool(challenger_agrees),
        }
        if tier is not None:
            core.append(row)
        elif conf >= .68 and challenger_agrees:
            row["reason"] = (
                "PPG projection disagrees" if pp is not None and not ppg_agrees
                else "Scoring confirmation unavailable" if not ppg_agrees
                else "Below core confirmation threshold"
            )
            candidates.append(row)
    core.sort(key=lambda x: (x["tier"], -x["probability"], x["game_id"]))
    candidates.sort(key=lambda x: (-x["probability"], x["game_id"]))
    used = {x["game_id"] for x in core[:cap]}
    potential = [x for x in candidates if x["game_id"] not in used]
    return {"core": core[:cap], "potential": potential[:max(0, min(addition_cap, cap-len(core[:cap])))],
            "reason": None}


def load_snapshot(season: int, week: int, root: Path = ARCHIVE_DIR) -> dict | None:
    """Reject untrusted, partial or modified JSON snapshots. Never regenerate past picks."""
    try:
        path = root / f"{int(season)}_week_{int(week):02d}.json"
        raw = json.loads(path.read_text())
        if (int(raw["season"]) != season or int(raw["week"]) != week
                or raw.get("history_is_pregame") is not True
                or not isinstance(raw.get("games"), list) or not raw["games"]):
            return None
        digest = hashlib.sha256(json.dumps(raw["games"], sort_keys=True).encode()).hexdigest()
        if digest != raw.get("snapshot_sha256"):
            return None
        when = pd.Timestamp(raw["created_at_utc"])
        if pd.isna(when) or when.tzinfo is None:
            return None
        ids = [str(g.get("game_id")) for g in raw["games"]]
        if len(ids) != len(set(ids)):
            return None
        return raw
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return None


def snapshot_is_pregame(snapshot: dict, slate: pd.DataFrame) -> bool:
    """Only trust archives created before the first game's *calendar date*.

    Date-only NFLverse game dates cannot establish the exact kickoff hour.
    """
    if slate is None or slate.empty or not isinstance(snapshot, dict):
        return False
    try:
        when = pd.Timestamp(snapshot["created_at_utc"])
        dates = pd.to_datetime(slate["gameday"], utc=True, errors="coerce")
        if when.tzinfo is None or dates.isna().any():
            return False
        # Complete slate only, not an unrelated game accidentally sharing an ID.
        if set(slate["game_id"].astype(str)) != {
            str(g["game_id"]) for g in snapshot["games"]
        }:
            return False
        for record in snapshot["games"]:
            row = slate.loc[slate["game_id"].astype(str) == str(record["game_id"])]
            if len(row) != 1:
                return False
            g = row.iloc[0]
            if (str(g["home_team"]) != str(record["home_team"])
                    or str(g["away_team"]) != str(record["away_team"])):
                return False
        return when.normalize() < dates.min().normalize()
    except (KeyError, ValueError, TypeError, OverflowError):
        return False


def grade(selected: list[dict], slate: pd.DataFrame) -> dict:
    """Grade archived teams only; no new picks from played games."""
    if slate is None or slate.empty:
        return {"wins":0,"losses":0,"ties":0,"pending":len(selected)}
    indexed = slate.set_index("game_id")
    results = {"wins":0,"losses":0,"ties":0,"pending":0}
    for pick in selected:
        key = pick["game_id"]
        if key not in indexed.index:
            results["pending"] += 1
            continue
        game = indexed.loc[key]
        if isinstance(game, pd.DataFrame):
            results["pending"] += 1
            continue
        a, h = _finite(game.get("away_score")), _finite(game.get("home_score"))
        if a is None or h is None or not bool(game.get("completed", False)):
            results["pending"] += 1
        elif a == h:
            results["ties"] += 1
        else:
            actual = str(game["home_team"]) if h > a else str(game["away_team"])
            results["wins" if actual == pick["team"] else "losses"] += 1
    return results


def historic_total(years=(2023, 2024, 2025)):
    records = [HISTORICAL["seasons"][year] for year in years]
    return {"wins":sum(x["wins"] for x in records),
            "losses":sum(x["losses"] for x in records)}


def history_rate(wins, losses):
    return f"{100*wins/(wins+losses):.1f}%" if wins+losses else "—"

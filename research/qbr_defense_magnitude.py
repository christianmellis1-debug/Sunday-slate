"""Magnitude study: do pregame QB QBR and scoring-defense gaps improve Elo?

The discovery window is 2019–2022. 2023–2025 is evaluated separately,
without altering the frozen NFL-ELO-1.0 model or selecting thresholds from it.

Inputs: nflverse schedules and ESPN weekly Total QBR, same chronological
week-frozen history reconstruction as research/test_qbr_defense.py.

Run: python -m research.qbr_defense_magnitude --output qbr_defense_magnitude.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

from research.test_qbr_defense import evaluate_games, load_games, load_qbr
from sunday_slate.model import predict_regular_season

TRAIN = (2019, 2020, 2021, 2022)
HOLDOUT = (2023, 2024, 2025)
CURRENT = (2026,)
# Values are specified before examining results of this magnitude study.
QBR_BINS = [(0, 5), (5, 10), (10, 20), (20, None)]
DEF_BINS = [(0, 3), (3, 7), (7, None)]
THRESHOLDS = [(0, 0), (5, 2), (10, 4), (15, 6), (20, 8),
              (5, 5), (10, 6), (15, 4), (20, 4), (10, 2)]


def records(games: pd.DataFrame, qbr: pd.DataFrame) -> pd.DataFrame:
    seasons = TRAIN + HOLDOUT + CURRENT
    base = evaluate_games(games, qbr, years=seasons, min_plays=30, min_def_games=1)
    frozen = predict_regular_season(games)
    if frozen.game_id.duplicated().any() or base.game_id.duplicated().any():
        raise ValueError("Duplicate game IDs in analysis")
    baseline = frozen.set_index("game_id")[["predicted_winner", "pick_probability"]]
    base = base.join(baseline, on="game_id", validate="one_to_one")
    if base.predicted_winner.isna().any():
        raise ValueError("Elo predictions missing for games included in evaluation")
    base["elo_correct"] = base.predicted_winner.eq(base.winning_team)
    base["qbr_gap"] = (base.home_pregame_qbr - base.away_pregame_qbr).abs()
    base["def_gap"] = (base.def_home_ppg_allowed - base.def_away_ppg_allowed).abs()
    base["qb_correct"] = base.qbr_team.eq(base.winning_team)
    base["def_correct"] = base.defense_team.eq(base.winning_team)
    return base


def _rate(subset: pd.DataFrame, team_col: str = "predicted_winner") -> dict:
    n = len(subset)
    wins = int(subset[team_col].eq(subset.winning_team).sum()) if n else 0
    return {"n": n, "wins": wins, "losses": n-wins,
            "rate": round(wins/n, 4) if n else None}


def bins_for(data: pd.DataFrame, feature: str, team: str,
             bins: list[tuple[float, float | None]]) -> list[dict]:
    available = data[data[team].notna() & data[feature].notna()]
    out=[]
    for lo, hi in bins:
        subset=available[available[feature].ge(lo)]
        if hi is not None:
            subset=subset[subset[feature].lt(hi)]
        conflict=subset[subset[team].ne(subset.predicted_winner)]
        same=subset[subset[team].eq(subset.predicted_winner)]
        out.append({
            "gap": f"{lo}–{hi if hi is not None else 'up'}",
            "metric_side": _rate(subset, team),
            "elo_same_games": _rate(subset),
            "metric_elo_disagree_n": len(conflict),
            "metric_on_elo_conflicts": _rate(conflict, team),
            "elo_on_conflicts": _rate(conflict),
            "metric_elo_agree_n": len(same),
            "elo_on_agreements": _rate(same),
        })
    return out


def pair_threshold(data: pd.DataFrame, qbr_min: int, def_min: int) -> dict:
    qualified = data[
        data.qbr_team.notna() & data.defense_team.notna() &
        data.qbr_team.eq(data.defense_team) &
        data.qbr_gap.ge(qbr_min) & data.def_gap.ge(def_min)
    ]
    conflict = qualified[qualified.qbr_team.ne(qualified.predicted_winner)]
    agreement = qualified[qualified.qbr_team.eq(qualified.predicted_winner)]
    signal = _rate(qualified, "qbr_team")
    elo = _rate(qualified)
    override = _rate(conflict, "qbr_team")
    return {
        "min_qbr_gap": qbr_min, "min_ppg_allowed_gap": def_min,
        "signal_wins": signal, "elo_same_games": elo,
        "all_three_agree": _rate(agreement),
        "two_factors_override_elo": override,
        "elo_on_override_games": _rate(conflict),
        "override_net_changed_correct": int(override["wins"] - (override["n"] - override["wins"])),
    }


def describe_period(data: pd.DataFrame, years: tuple[int, ...]) -> dict:
    s = data[data.season.isin(years)]
    return {
        "years":list(years),
        "graded_games":len(s),
        "elo_all_games":_rate(s),
        "qbr_bins":bins_for(s,"qbr_gap","qbr_team",QBR_BINS),
        "defense_bins":bins_for(s,"def_gap","defense_team",DEF_BINS),
        "joint_gap_thresholds":[pair_threshold(s,q,d) for q,d in THRESHOLDS],
    }


def choose_discovery_rule(discovery: dict) -> dict | None:
    """Choose ONLY from 2019–22. Min 25 override examples, +5 changed correct.

    This is exploratory! Repeated threshold comparison is multiple testing.
    The holdout remains an evaluation cohort, not input to selection.
    """
    candidates = [r for r in discovery["joint_gap_thresholds"]
                  if r["two_factors_override_elo"]["n"] >= 25
                  and r["override_net_changed_correct"] >= 5]
    if not candidates:
        return None
    return max(candidates, key=lambda r: (
        r["override_net_changed_correct"], r["two_factors_override_elo"]["n"],
        -r["min_qbr_gap"]-r["min_ppg_allowed_gap"]))


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--games",default=None)
    parser.add_argument("--qbr",default=None)
    parser.add_argument("--output",default=None)
    args=parser.parse_args()
    frame=records(load_games(args.games),load_qbr(args.qbr))
    train=describe_period(frame,TRAIN)
    holdout=describe_period(frame,HOLDOUT)
    ytd=describe_period(frame,CURRENT)
    selected=choose_discovery_rule(train)
    confirmation=None
    if selected:
        confirmation=pair_threshold(frame[frame.season.isin(HOLDOUT)],
                                    selected["min_qbr_gap"],selected["min_ppg_allowed_gap"])
    result={
        "definitions": {
            "qbr": "Last 4 prior weeks, ESPN Total QBR weighted by QB plays, highest-use previous QB (min 30 plays); NOT verified next starter",
            "defense": "Lower same-season opponents' points allowed per game in preceding completed weeks",
            "elo": "Unmodified Sunday Slate NFL-ELO-1.0, warmup history from 2014",
            "games": "Decisive completed regular-season games; historical releases not timestamped as-of each game",
            "selection": "Search of ten predeclared qbr/defense gap pairs in 2019–2022 only; require >=25 conflicts and gain >=5 correctly picked vs Elo",
            "qualifier": "Signals both agree with each other; group is split on whether they also agree with Elo",
        },
        "discovery_2019_2022":train,
        "holdout_2023_2025":holdout,
        "diagnostic_2026_ytd":ytd,
        "selected_training_only_rule":selected and {"min_qbr_gap":selected["min_qbr_gap"],
                                                 "min_ppg_allowed_gap":selected["min_ppg_allowed_gap"]},
        "selected_rule_holdout":confirmation,
        "recommendation": "Do not change the existing Elo model on retrospective selection alone.",
    }
    print(json.dumps(result,indent=2,allow_nan=False))
    if args.output:
        Path(args.output).write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")


if __name__=="__main__":
    main()

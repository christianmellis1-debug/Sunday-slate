"""Phase 4 reproducible, research-only model and candidate waterfall.

NO production model imports this module. No sportsbook odds are used.
Training periods are fixed at 2019–2022. 2023–2025 are retrospective
evaluation periods already inspected during research, and 2026 onward is
preliminary prospective-style evaluation, not an untouched future holdout.

Usage:
    python -m backtests.experimental_research --csv path/to/games.csv
    python -m backtests.experimental_research --output phase4_results.json

No same-week or future game results may enter a prediction.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import pandas as pd

from sunday_slate.model import predict_regular_season

TRAIN_YEARS = frozenset(range(2019, 2023))
RETROSPECTIVE_YEARS = frozenset((2023, 2024, 2025))
SHRINK_PRIOR_GAMES = 4
HOME_PPG_CONTEXT_POINTS = 2.0
RIDGE_PENALTY = 0.025
REQUIRED = frozenset({
    "game_id", "season", "week", "game_type", "home_team", "away_team",
    "home_score", "away_score", "location",
})


def preweek_features(schedule: pd.DataFrame) -> pd.DataFrame:
    """Calculate season-local team scoring signals from PRIOR WEEKS ONLY.

    All games in a given week are captured before any that week's results
    enter the history, including Thursday/Saturday/Sunday/Monday games.
    """
    missing = REQUIRED - set(schedule)
    if missing:
        raise ValueError("Missing required schedule columns: " + ", ".join(sorted(missing)))
    games = schedule[schedule["game_type"].eq("REG")].copy()
    if games["game_id"].isna().any() or games["game_id"].duplicated().any():
        raise ValueError("Missing/duplicate regular-season game IDs")
    games["season"] = pd.to_numeric(games["season"], errors="coerce")
    games["week"] = pd.to_numeric(games["week"], errors="coerce")
    games["home_score"] = pd.to_numeric(games["home_score"], errors="coerce")
    games["away_score"] = pd.to_numeric(games["away_score"], errors="coerce")
    games = games[games["season"].ge(2014) & games["week"].ge(1)].copy()
    games = games.sort_values(["season", "week", "game_id"], kind="stable")
    records: list[dict] = []

    for (season, season_games) in games.groupby("season", sort=True):
        # This is reset every season: no mistaken current-season scoring
        # history carried over across January / February.
        history: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for (_, week), slate in season_games.groupby(["season", "week"], sort=True):
            played_this_week = []
            for game in slate.to_dict("records"):
                home = str(game["home_team"])
                away = str(game["away_team"])
                h_games = history[home]
                a_games = history[away]
                n = min(len(h_games), len(a_games))
                neutral = "neutral" in str(game["location"]).lower()

                recent_home = h_games[-4:]
                recent_away = a_games[-4:]
                h_margin = sum(p - a for p, a in recent_home) / len(recent_home) if recent_home else 0.0
                a_margin = sum(p - a for p, a in recent_away) / len(recent_away) if recent_away else 0.0
                recent_margin_feature = (
                    (h_margin - a_margin + (0.0 if neutral else HOME_PPG_CONTEXT_POINTS))
                    * n / (n + SHRINK_PRIOR_GAMES) / 10.0
                )

                ppg_margin = None
                if n:
                    h_off = sum(p for p, _ in h_games) / len(h_games)
                    h_allowed = sum(a for _, a in h_games) / len(h_games)
                    a_off = sum(p for p, _ in a_games) / len(a_games)
                    a_allowed = sum(a for _, a in a_games) / len(a_games)
                    ppg_margin = ((h_off + a_allowed) - (a_off + h_allowed)) / 2
                    if not neutral:
                        ppg_margin += HOME_PPG_CONTEXT_POINTS

                records.append({
                    "game_id": str(game["game_id"]),
                    "min_prior_games": n,
                    "recent_margin_feature": recent_margin_feature,
                    "ppg_projected_margin": ppg_margin,
                })
                hs, aws = game["home_score"], game["away_score"]
                if pd.notna(hs) and pd.notna(aws):
                    played_this_week.append((home, away, float(hs), float(aws)))
            # Update only after every game in this week has been projected.
            for home, away, hs, aws in played_this_week:
                history[home].append((hs, aws))
                history[away].append((aws, hs))
    return pd.DataFrame(records, columns=[
        "game_id", "min_prior_games", "recent_margin_feature", "ppg_projected_margin"
    ])


def research_games(schedule: pd.DataFrame) -> pd.DataFrame:
    """Merge Elo forecasts and independently frozen scoring features."""
    predicted = predict_regular_season(schedule)
    if predicted.empty:
        return pd.DataFrame()
    features = preweek_features(schedule)
    merged = predicted.merge(features, on="game_id", validate="one_to_one")
    valid = merged[merged["pick_result"].isin(["Correct", "Incorrect"])].copy()
    valid["actual_home_win"] = (valid["pick_result"].eq("Correct")
                               == valid["predicted_winner"].eq(valid["home_team"]))
    valid["elo_difference_100"] = (
        valid["home_elo"] - valid["away_elo"]
        + valid["home_field_elo"] + valid["rest_elo"]
    ) / 100
    return valid


def _sigmoid(z: float) -> float:
    z = max(-35., min(35., z))
    return 1 / (1 + math.exp(-z))


def fit_recent_form_model(training: pd.DataFrame, penalty: float = RIDGE_PENALTY) -> tuple[float, float, float]:
    """Deterministic diagonal-Newton regularized logistic research fit.

    Fixed feature scales, penalty, and seasons. Optimization sees training
    games only; it never uses any 2023+ result to select coefficients.
    """
    if training.empty or not set(training["season"].unique()).issubset(TRAIN_YEARS):
        raise ValueError("Training must use only 2019–2022 graded games")
    x = [(1., float(r.elo_difference_100), float(r.recent_margin_feature))
         for r in training.itertuples(index=False)]
    y = [1 if bool(v) else 0 for v in training["actual_home_win"]]
    w = [0., 0., 0.]
    n = len(x)
    for _ in range(1000):
        gradients = [0., 0., 0.]
        diagonals = [0., 0., 0.]
        for row, result in zip(x, y):
            p = _sigmoid(sum(a * b for a, b in zip(row, w)))
            err, mass = p - result, p * (1 - p)
            for j in range(3):
                gradients[j] += err * row[j]
                diagonals[j] += mass * row[j] ** 2
        delta = 0.
        for j in range(3):
            reg = 0. if j == 0 else penalty
            gradient = gradients[j] / n + reg * w[j]
            hess = diagonals[j] / n + reg
            step = .15 * max(-.15, min(.15, gradient / max(.0001, hess)))
            w[j] -= step
            delta = max(delta, abs(step))
        if delta < 1e-6:
            break
    return tuple(w)


def tier_name(row) -> str:
    """One and only one football-only, mutually exclusive research tier."""
    confidence = float(row.pick_probability)
    ppg = row.ppg_projected_margin
    margin_available = pd.notna(ppg) and abs(float(ppg)) > 1e-9
    agreement = (margin_available
                 and (float(ppg) > 0) == (float(row.home_probability) >= .5))
    if confidence >= .75:
        return "Tier 1 - Heavy Favorite"
    if int(row.min_prior_games) >= 3 and agreement and confidence >= .60:
        if abs(float(ppg)) >= 7:
            return "Tier 2 - Double Confirmation"
        return "Tier 3 - Solid Consensus"
    return "Tier 4 - Uncertain"


def report_record(frame: pd.DataFrame, column: str) -> dict:
    """Count straight-up decisions (never ATS, never ROI)."""
    if frame.empty:
        return {"games": 0, "wins": 0, "losses": 0, "accuracy": None}
    predicted_home = pd.to_numeric(frame[column], errors="coerce").ge(.5)
    actual_home = frame["actual_home_win"].astype(bool)
    wins = int(predicted_home.eq(actual_home).sum())
    n = len(frame)
    return {"games": n, "wins": wins, "losses": n - wins, "accuracy": round(wins / n, 4)}


def run(schedule: pd.DataFrame) -> dict:
    rows = research_games(schedule)
    if rows.empty:
        raise ValueError("No completed decisive games to evaluate")
    train = rows[rows["season"].isin(TRAIN_YEARS)].copy()
    if train.empty:
        raise ValueError("No 2019–2022 training data")
    coefficients = fit_recent_form_model(train)
    x = (coefficients[0]
         + coefficients[1] * rows["elo_difference_100"]
         + coefficients[2] * rows["recent_margin_feature"])
    rows["experimental_probability"] = x.map(_sigmoid)
    rows["tier"] = [tier_name(row) for row in rows.itertuples(index=False)]

    def by_period(years):
        sample = rows[rows["season"].isin(years)]
        return {
            "baseline": report_record(sample, "home_probability"),
            "recent_form_experiment": report_record(sample, "experimental_probability"),
            "tiers": {
                label: report_record(group, "home_probability")
                for label, group in sample.groupby("tier")
            },
        }
    return {
        "status": "RESEARCH_ONLY_NOT_DEPLOYED",
        "model": "NFL-ELO-1.0 + fixed 4-game scoring margin",
        "fit_years": sorted(TRAIN_YEARS),
        "previously_inspected_years": sorted(RETROSPECTIVE_YEARS),
        "coefficients": list(coefficients),
        "periods": {
            "2019-2022_training": by_period(TRAIN_YEARS),
            "2023-2025_retrospective": by_period(RETROSPECTIVE_YEARS),
            "2026_preliminary": by_period([2026]),
        },
        "season_details": {str(year): by_period([year])
                           for year in range(2019, 2027)},
        "limitations": [
            "2023-2025 have been inspected during research and must not be described as pristine holdout validation.",
            "2026 is incomplete; as results arrive its scores change.",
            "No player injury, verified starting QB, opponent-adjusted EPA, or authenticated DraftKings odds are included.",
            "Candidate tiers select games; their higher win rate does not improve all-game accuracy or establish betting ROI.",
            "Recent-form logistic model does not replace production NFL-ELO-1.0.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", help="Local nflverse schedule CSV; recommended for reproducibility")
    parser.add_argument("--output", help="JSON report path (optional)")
    args = parser.parse_args()
    if args.csv:
        schedule = pd.read_csv(args.csv)
    else:
        from sunday_slate.data import load_schedules
        schedule = load_schedules()
    result = run(schedule)
    output = json.dumps(result, indent=2, allow_nan=False)
    print(output)
    if args.output:
        Path(args.output).write_text(output + "\n")


if __name__ == "__main__":
    main()

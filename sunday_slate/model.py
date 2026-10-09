"""Sunday Slate NFL win-probability model v1.0.

Historically selected parameters: 2019-2022 regular seasons ONLY.
Independent season-level holdouts: 2023, 2024, 2025, 2026 YTD.

Forecast every game in a given NFL week from ratings frozen at the start of
that week. Update ratings AFTER all the week's results are graded. This keeps
all model inputs strictly earlier than the predicted week, even when a Thursday
night game finishes before the remaining Sunday games.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import pandas as pd

VERSION = "NFL-ELO-1.0"
REQUIRED = frozenset({
    "game_id", "season", "week", "game_type", "home_team", "away_team",
    "home_score", "away_score",
})


@dataclass(frozen=True)
class Parameters:
    initial: float = 1500.0
    k_factor: float = 36.0
    home_advantage: float = 30.0
    offseason_retention: float = 0.75
    probability_temperature: float = 0.80
    rest_elo_per_day: float = 3.0
    mov_weight: float = 0.70


DEFAULT = Parameters()


def probability(elo_difference: float, params: Parameters = DEFAULT) -> float:
    """Elo logistic with an empirically selected, fixed temperature."""
    exponent = math.log(10.0) * (float(elo_difference) / 400.0) * params.probability_temperature
    return 1.0 / (1.0 + math.exp(-max(-35.0, min(35.0, exponent))))


def _expected_rating(diff: float) -> float:
    exponent = math.log(10.0) * (diff / 400.0)
    return 1.0 / (1.0 + math.exp(-max(-35.0, min(35.0, exponent))))


def _rest_bonus(game, params: Parameters) -> float:
    home, away = pd.to_numeric(game.get("home_rest"), errors="coerce"), pd.to_numeric(game.get("away_rest"), errors="coerce")
    if pd.isna(home) or pd.isna(away):
        return 0.0
    return float(max(-7.0, min(7.0, home - away))) * params.rest_elo_per_day


def _game_bonus(game, params: Parameters) -> tuple[float, float]:
    neutral = "neutral" in str(game.get("location", "")).casefold()
    rest = _rest_bonus(game, params)
    return (0.0 if neutral else params.home_advantage), rest


def predict_regular_season(schedule: pd.DataFrame, params: Parameters = DEFAULT, first_season: int = 2014) -> pd.DataFrame:
    """Produce pregame snapshots, including completed games for retrospective scoring.

    Missing or duplicated identifiers fail closed instead of inventing picks.
    Week-group update order is deterministic, and ties do not update ratings.
    Non-regular-season games are intentionally excluded pending postseason validation.
    """
    missing = REQUIRED.difference(schedule.columns)
    if missing:
        raise ValueError(f"Missing model columns: {', '.join(sorted(missing))}")
    games = schedule.copy()
    games["season"] = pd.to_numeric(games["season"], errors="coerce")
    games["week"] = pd.to_numeric(games["week"], errors="coerce")
    games = games[(games["game_type"] == "REG") & (games["season"] >= first_season) & games["week"].ge(1)]
    if games.empty:
        return pd.DataFrame(columns=["game_id", "season", "week", "home_probability", "away_probability", "predicted_winner", "pick_probability", "pick_correct", "pick_result", "model_version"])
    if games["game_id"].isna().any() or games["game_id"].duplicated().any():
        raise ValueError("Regular season schedule has missing/duplicate game IDs")
    if games[["home_team", "away_team"]].isna().any().any():
        raise ValueError("Regular season schedule has missing teams")
    games["home_score"] = pd.to_numeric(games["home_score"], errors="coerce")
    games["away_score"] = pd.to_numeric(games["away_score"], errors="coerce")
    games = games.sort_values(["season", "week", "game_id"], kind="stable")
    ratings: dict[str, float] = {}
    output: list[dict] = []
    last_season = None

    for (season, week), slate in games.groupby(["season", "week"], sort=True):
        if season != last_season:
            for team, old in list(ratings.items()):
                ratings[team] = params.initial + (old - params.initial) * params.offseason_retention
            last_season = season

        predictions = []
        for game in slate.to_dict("records"):
            home, away = str(game["home_team"]), str(game["away_team"])
            h_elo = ratings.get(home, params.initial)
            a_elo = ratings.get(away, params.initial)
            home_field, rest = _game_bonus(game, params)
            expected = _expected_rating(h_elo - a_elo + home_field + rest)
            p_home = probability(h_elo - a_elo + home_field + rest, params)
            winner = home if p_home >= 0.50 else away
            home_score, away_score = game["home_score"], game["away_score"]
            final = pd.notna(home_score) and pd.notna(away_score)
            tie = final and home_score == away_score
            correct = None if not final or tie else bool((home_score > away_score) == (winner == home))
            record = {
                "game_id": str(game["game_id"]), "season": int(season), "week": int(week),
                "home_team": home, "away_team": away, "home_elo": h_elo, "away_elo": a_elo,
                "home_field_elo": home_field, "rest_elo": rest,
                "home_probability": p_home, "away_probability": 1 - p_home,
                "predicted_winner": winner, "pick_probability": max(p_home, 1 - p_home),
                "pick_correct": correct,
                "pick_result": ("Push" if tie else "Correct" if correct is True else "Incorrect" if correct is False else "Pending"),
                "model_version": VERSION,
            }
            predictions.append((record, expected, game))
            output.append(record)

        # Freeze each week's predictions before updating any ratings.
        for prediction, expectation, game in predictions:
            home_score, away_score = game["home_score"], game["away_score"]
            if pd.isna(home_score) or pd.isna(away_score) or home_score == away_score:
                continue
            outcome = 1.0 if home_score > away_score else 0.0
            margin_factor = 1.0 + (min(28.0, abs(home_score - away_score)) / 28.0) * params.mov_weight
            delta = params.k_factor * (outcome - expectation) * margin_factor
            home, away = prediction["home_team"], prediction["away_team"]
            ratings[home] = prediction["home_elo"] + delta
            ratings[away] = prediction["away_elo"] - delta
    return pd.DataFrame(output)


def summary(predictions: pd.DataFrame, season: int | None = None) -> dict:
    """Summarize decisive completed games; exclude ties and unplayed fixtures."""
    x = predictions if season is None else predictions[predictions["season"] == season]
    graded = x[x["pick_result"].isin(["Correct", "Incorrect"])]
    wins = int(graded["pick_result"].eq("Correct").sum())
    n = len(graded)
    if not n:
        return {"games": 0, "wins": 0, "losses": 0, "accuracy": None, "brier": None, "logloss": None}
    actual = ((graded["pick_result"] == "Correct") == (graded["predicted_winner"] == graded["home_team"])).astype(float)
    probs = pd.to_numeric(graded["home_probability"], errors="coerce").clip(1e-10, 1 - 1e-10)
    return {
        "games": n, "wins": wins, "losses": n - wins,
        "accuracy": wins / n,
        "brier": float(((actual - probs) ** 2).mean()),
        "logloss": float((-actual * probs.map(math.log) - (1 - actual) * (1 - probs).map(math.log)).mean()),
    }


def rationale(row: pd.Series) -> str:
    """Football-language explanation restricted to factors the model actually uses."""
    team = str(row["predicted_winner"])
    home = str(row["home_team"])
    away = str(row["away_team"])
    home_elo, away_elo = float(row["home_elo"]), float(row["away_elo"])
    advantage = home_elo - away_elo if team == home else away_elo - home_elo
    sentences = []
    if advantage > 20:
        sentences.append(f"{team} enters with a stronger results-based team rating.")
    elif advantage < -20:
        sentences.append(f"{team} faces a stronger-rated opponent, so this is a more uncertain pick.")
    else:
        sentences.append("These teams have similar recent results-based ratings.")
    if float(row["home_field_elo"]) > 0:
        sentences.append(f"{home} also gets a home-field adjustment.")
    rest = float(row["rest_elo"])
    if abs(rest) > 0:
        sentences.append(f"{'Home' if rest > 0 else 'Road'} team has more rest entering this matchup.")
    sentences.append("Quarterback availability, injuries, and sportsbook odds are not yet included.")
    return " ".join(sentences)

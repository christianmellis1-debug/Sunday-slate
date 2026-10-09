"""NFL run-defense EPA vs weak rushing-offense EPA: controlled historical test.

The calculation uses prior-week EPA PER CARRY. Rushing EPA is a *sum* in the
nflverse weekly team box; carries is the denominator. For defensive rush EPA
allowed, we use the opposing team's own rushing EPA/carries in the same prior
game, not a season-ending defensive ranking. Lower allowed EPA is better.
Negative offensive rush EPA/carry is worse.

Discovery years: 2019–2022. Later evaluation: 2023–2025. 2026 YTD diagnostic.
Quarterile (25%) is fixed a priori, with 20/33/40 percent sensitivity checks.
No rule modifies the Sunday Slate NFL Elo engine.

Usage: python -m research.run_defense_rush_epa --output rush_epa_results.json

The shared research engine works with summed numeric rushing values. This
adapter passes summed rushing EPA through its yardage-compatible accumulator,
then renames every result column to its actual EPA interpretation. No rushing
yards are used to qualify games.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from research.run_defense_rush import (
    REQUIRED_STATS, TRAIN, HOLDOUT, CURRENT, THRESHOLDS, MIN_GAMES,
    study as historical_study, results as historical_results,
    select_training_rule,
)
from research.test_qbr_defense import load_games

EPA_REQUIRED = (REQUIRED_STATS - {"rushing_yards"}) | {"rushing_epa"}
SOURCE_LABELS = {
    "run_defense_ypc_allowed": "run_defense_epa_allowed_per_carry",
    "opponent_rushing_ypc": "opponent_rushing_epa_per_carry",
    "rush_defense_cutoff": "defense_epa_allowed_cutoff",
    "rush_offense_cutoff": "weak_offense_epa_cutoff",
}


def load_rush_epa(path: str | None = None) -> pd.DataFrame:
    if path:
        source = pd.read_csv(path, low_memory=False)
    else:
        import nflreadpy
        source = pd.DataFrame(nflreadpy.load_team_stats(
            seasons=list(TRAIN + HOLDOUT + CURRENT),
            summary_level="week"
        ).to_dicts())
    missing = EPA_REQUIRED.difference(source.columns)
    if missing:
        raise ValueError("Weekly NFL team EPA feed missing required columns: "
                         + ", ".join(sorted(missing)))
    data = source.copy()
    for col in ("season", "week", "rushing_epa", "carries"):
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data = data[data.season.isin(TRAIN + HOLDOUT + CURRENT) &
                data.season_type.eq("REG")].copy()
    data = data[data.carries.gt(0) & data.rushing_epa.notna()].copy()
    # Reusing the shared pregame aggregation engine with a summed *EPA* value:
    # never mix actual rushing yard totals into the selection.
    data["rushing_yards"] = data["rushing_epa"].astype(float)
    data["team"] = data["team"].astype(str).str.upper()
    data["opponent_team"] = data["opponent_team"].astype(str).str.upper()
    if data.duplicated(["game_id", "team"]).any():
        raise ValueError("NFL weekly EPA feed has duplicate team/game records")
    return data


def test_epa_scenario(games: pd.DataFrame, epa: pd.DataFrame) -> pd.DataFrame:
    """Return eligible games, with columns correctly labeled as EPA/carry."""
    source = historical_study(games, epa, min_games=MIN_GAMES)
    out = source.rename(columns=SOURCE_LABELS)
    out.attrs.update(source.attrs)
    return out


def choose(train: list[dict], holdout: list[dict]) -> tuple[dict | None, dict | None]:
    chosen = select_training_rule(train)
    if chosen is None:
        return None, None
    validated = next((x for x in holdout if x["quantile"] == chosen["quantile"]), None)
    return chosen, validated


def make_report(games: pd.DataFrame, epa: pd.DataFrame) -> dict:
    graded = test_epa_scenario(games, epa)
    if graded.empty:
        raise RuntimeError("No eligible matchup cases: cannot report a backtest")
    train = historical_results(graded, TRAIN)
    holdout = historical_results(graded, HOLDOUT)
    current = historical_results(graded, CURRENT)
    chosen, validation = choose(train, holdout)
    return {
        "definition": (
            "Prior game-week NFL offensive rushing EPA divided by rushing carries; "
            "defensive rushing EPA allowed from prior opposing team same-game EPA/carries. "
            "At least 3 earlier games per team. Strong run defense = lowest quartile "
            "of league rush EPA allowed/carry; weak rushing offense = lowest quartile "
            "of league rush EPA/carry. Rankings re-established before each week. "
            "One side only; no current/future scores or performance in features."
        ),
        "split": {"discovery": list(TRAIN), "evaluation": list(HOLDOUT),
                  "preliminary": list(CURRENT)},
        "data_caveats": (
            "EPA is model-derived, may be revised retrospectively, depends on play context; "
            "historical spread_line is a reference closing line without independently verified "
            "bettable pre-kickoff time/price; ATS record is not actual ROI. "
            "Elo unchanged; no starter/injury adjustment. "
            "Non-rushing team QB kneels/scrambles may affect play classification."
        ),
        "coverage": graded.attrs.get("coverage"),
        "source_epa_valid_lines": int(len(epa)),
        "discovery_2019_2022": train,
        "holdout_2023_2025": holdout,
        "diagnostic_2026_ytd": current,
        "selected_on_discovery_only": chosen,
        "selected_rule_validation": validation,
        "policy": "Only recommend an Elo override if discovery and untouched holdout show repeatable predictive gains; a high win rate alone is not proof of betting value.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", help="Optional locally pinned nflverse schedules CSV")
    parser.add_argument("--epa", help="Optional locally pinned NFLverse weekly team stats CSV")
    parser.add_argument("--output", help="Output JSON for archival")
    options = parser.parse_args()
    games = load_games(options.games)
    epa = load_rush_epa(options.epa)
    print("EPA YEARS:", epa.groupby("season").size().to_dict(), flush=True)
    report = make_report(games, epa)
    print("EPA_STUDY_JSON_BEGIN")
    print(json.dumps(report, indent=2, allow_nan=False))
    print("EPA_STUDY_JSON_END", flush=True)
    if options.output:
        Path(options.output).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()

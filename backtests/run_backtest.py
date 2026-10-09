"""Reproduce NFL-ELO-1.0 holdout scores from the current nflverse schedule.

Usage: python -m backtests.run_backtest
Optional: python -m backtests.run_backtest --csv /path/to/games.csv
Works without any sportsbook odds or paid API. Never re-fit on holdouts.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import pandas as pd

from sunday_slate.model import DEFAULT, Parameters, VERSION, predict_regular_season, summary


def get_schedule(path: str | None) -> pd.DataFrame:
    if path:
        return pd.read_csv(path)
    from sunday_slate.data import load_schedules
    return load_schedules()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=None, help="Local nflverse schedules CSV")
    parser.add_argument("--output", default=None, help="Optional path to save JSON metrics")
    args = parser.parse_args()
    data = get_schedule(args.csv)
    tuned = predict_regular_season(data)
    baseline = predict_regular_season(data, params=Parameters(k_factor=20.0, home_advantage=50.0, offseason_retention=.75, probability_temperature=1., rest_elo_per_day=0., mov_weight=0.))
    report = {
        "version": VERSION,
        "params": DEFAULT.__dict__,
        "training_years": [2019,2020,2021,2022],
        "holdout_years": [2023,2024,2025],
        "training_metrics": summary(tuned[tuned["season"].isin([2019,2020,2021,2022])]),
        "baseline_training_metrics": summary(baseline[baseline["season"].isin([2019,2020,2021,2022])]),
        "holdout": {
            str(year): {"model": summary(tuned, year), "baseline": summary(baseline, year)}
            for year in [2023,2024,2025,2026]
        },
        "combined_2023_2025": summary(tuned[tuned["season"].isin([2023,2024,2025])]),
        "combined_2023_2026_ytd": summary(tuned[tuned["season"].isin([2023,2024,2025,2026])]),
        "limitations": "Fixed tuned hyperparameters; season 2026 incomplete. Scores count decisive completed regular-season games only; no spread or moneyline ROI. NFL team rating and rest do not capture injuries or quarterback changes.",
    }
    raw = json.dumps(report, indent=2, allow_nan=False)
    print(raw)
    if args.output:
        Path(args.output).write_text(raw + "\n")


if __name__ == "__main__":
    main()

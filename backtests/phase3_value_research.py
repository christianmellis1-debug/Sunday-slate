"""Phase 3 historical moneyline research: REFERENCE prices, not verified pregame odds.

Usage: python -m backtests.phase3_value_research
       python -m backtests.phase3_value_research --csv ./games.csv

A positive edge here is ONLY model probability minus the no-vig market estimate.
The nflverse schedule's market prices have no verified pre-kickoff quote timestamp.
This report MUST NOT be described as a prospective/deployable bet record.
"""
from __future__ import annotations

import argparse
import pandas as pd

from sunday_slate.data import load_schedules
from sunday_slate.model import predict_regular_season
from sunday_slate.market import historical_report, historical_screen


def report(schedules: pd.DataFrame, preds: pd.DataFrame, edge: float) -> None:
    selection = historical_screen(schedules, preds, edge=edge, seasons=(2023, 2024, 2025))
    all_years = historical_report(selection)
    print(f"Exploratory reference screen: minimum vig-free edge {edge:.0%}; model probability >=60%; odds -300 through +200")
    print(f"  2023–2025: {all_years['wins']}-{all_years['losses']} | bets={all_years['bets']} | flat stake ROI={all_years['roi']:+.2%}" if all_years['roi'] is not None else "  No data")
    for y in (2023, 2024, 2025):
        subset = selection[selection["season"].eq(y)]
        out = historical_report(subset)
        print(f"  {y}: {out['wins']}-{out['losses']} | units={out['units']:+.2f} | ROI={out['roi']:+.2%}" if out['roi'] is not None else f"  {y}: No selections")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", help="Optional local nflverse schedules CSV", default=None)
    args = parser.parse_args()
    schedules = pd.read_csv(args.csv) if args.csv else load_schedules()
    predictions = predict_regular_season(schedules)
    print("WARNING: Odds are unverified historical schedule reference prices, not executable pregame quotes. This is not realized ROI.")
    for edge in (.03, .05, .08):
        report(schedules, predictions, edge)


if __name__ == "__main__":
    main()

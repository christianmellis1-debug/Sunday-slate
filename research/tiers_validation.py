"""Research-only four-tier NFL waterfall validation against pinned EPA-form candidate.

All categories are mutually exclusive and graded on the SAME full-slate
Elo-based prediction. No spread, sportsbook or ROI assumptions.
The 2023-25 evaluation years have already been inspected repeatedly.
"""
import argparse
import json
from pathlib import Path

import pandas as pd

from research.frozen_weekly import predictions, load_frozen
from research.model_epa_qbr_study import load_stats
from sunday_slate.data import load_schedules

TIER_NAMES = [
    "Tier 1 | Heavy Favorite",
    "Tier 2 | Double Confirmation",
    "Tier 3 | Solid Consensus",
    "Tier 4 | Uncertain",
]


def classify(row):
    """Waterfall: strict first-match-wins; old Elo selection remains unchanged."""
    conf = float(row["pick_probability"])
    pp = row.get("ppg_projected_margin")
    eligible = (int(row["min_prior_games"]) >= 3
                and pd.notna(pp)
                and abs(float(pp)) > 1.e-9
                and (float(pp) > 0) == (float(row["home_probability"]) >= .5))
    if conf >= .75:
        return TIER_NAMES[0]
    if eligible and conf >= .60:
        return TIER_NAMES[1] if abs(float(pp)) >= 7 else TIER_NAMES[2]
    return TIER_NAMES[3]


def record(frame, field):
    n = len(frame)
    if not n:
        return {"n":0, "wins":0, "losses":0, "pct":None}
    wins = int(frame[field].astype(bool).sum())
    return {"n":n, "wins":wins, "losses":n-wins, "pct":round(100*wins/n,1)}


def summarize(grades, label, rule=lambda r: True):
    subset = grades[grades.apply(rule, axis=1)]
    a = record(subset, "elo_correct")
    b = record(subset, "challenger_correct")
    a["coverage_pct"] = round(100*len(subset)/len(grades),1) if len(grades) else None
    return {"filter":label, "elo":a, "frozen_candidate":b,
            "net_candidate_additional_wins":b["wins"]-a["wins"]}


def report(schedule, team):
    cfg = load_frozen()
    joined = predictions(schedule, team, cfg)
    x = joined[joined.pick_result.isin(["Correct","Incorrect"])].copy()
    x["elo_correct"] = x.pick_result.eq("Correct")
    x["challenger_correct"] = (
        x.challenger_winner.eq(x.home_team)
        == ((x.pick_result.eq("Correct")) == x.predicted_winner.eq(x.home_team))
    )
    x["tier"] = x.apply(classify, axis=1)
    x["candidate_elo_agree"] = x.challenger_winner.eq(x.predicted_winner)
    x["ppg_agree"] = (
        x.ppg_projected_margin.notna() &
        x.ppg_projected_margin.abs().gt(1.e-9) &
        x.ppg_projected_margin.gt(0).eq(x.home_probability.ge(.5))
    )
    def portion(grades):
        if grades.empty:
            return {}
        results = [summarize(grades, label,
                   lambda row, label=label:row.tier==label)
                   for label in TIER_NAMES]
        return {
            "baseline_elo":record(grades,"elo_correct"),
            "candidate":record(grades,"challenger_correct"),
            "all_tiers":results,
            "tiers_1_to_3":summarize(grades,"Tiers 1-3",
                                   lambda r:r.tier!=TIER_NAMES[3]),
            "confidence_75_plus":summarize(grades,"Elo confidence >=75%",
                                   lambda r:r.pick_probability>=.75),
            "model_agreement":summarize(grades,"Elo and frozen challenger agree",
                                   lambda r:bool(r.candidate_elo_agree)),
            "model_conflict":summarize(grades,"Elo and frozen challenger disagree",
                                   lambda r:not bool(r.candidate_elo_agree)),
            "ppg_disagreement":summarize(grades,"Elo and PPG disagree; >=3 games each",
                                   lambda r:int(r.min_prior_games)>=3 and
                                   pd.notna(r.ppg_projected_margin) and
                                   abs(float(r.ppg_projected_margin))>1.e-9 and
                                   not bool(r.ppg_agree)),
            "triple_confirmation":summarize(grades,"Elo, PPG, challenger agree; >=3 games each",
                                   lambda r:int(r.min_prior_games)>=3 and
                                   bool(r.ppg_agree) and bool(r.candidate_elo_agree)),
            "tier1_to_3_candidate_agree":summarize(grades,"Tier 1-3 AND candidate agrees",
                                   lambda r:r.tier!=TIER_NAMES[3] and bool(r.candidate_elo_agree)),
        }
    periods = {
        "2019_2022_training":[2019,2020,2021,2022],
        "2023_2025_retrospective":[2023,2024,2025],
        "2026_preliminary":[2026],
    }
    periods.update({str(y):[y] for y in range(2019,2027)})
    out = {k:portion(x[x.season.isin(years)]) for k,years in periods.items()}
    return {
        "model_version":cfg["version"],
        "status":"research only; no change to deployed app",
        "rules":TIER_NAMES,
        "data_rows":len(x),
        "periods":out,
        "restrictions": [
            "2023-2025 were repeatedly inspected and are not an untouched holdout",
            "2026 preliminary is incomplete and may use subsequently revised sources",
            "Betting lines and ROI excluded; only DraftKings is allowed for future market tests",
            "Qualifying tiers select higher-confidence games; selective win rates are not whole-slate model gains",
            "All categories mutually exclusive; candidate does not influence tier ranking",
        ],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output",default="tiers_research_results.json")
    args = p.parse_args()
    print("Loading NFL schedules and weekly team efficiency history",flush=True)
    result = report(load_schedules(),load_stats())
    output = json.dumps(result,indent=2,allow_nan=False)
    print("TIER_RESEARCH_RESULTS_BEGIN")
    print(output)
    print("TIER_RESEARCH_RESULTS_END",flush=True)
    Path(args.output).write_text(output+"\n")


if __name__ == "__main__":
    main()

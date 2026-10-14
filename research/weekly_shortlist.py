"""Research-only NFL weekly selection benchmarks; all signals pregame and season-local.

This ranks teams to win outright, NOT against the spread; none of the historical
retrospective outcomes is used to choose a team's selection before kickoff.
Scores are computed only after each week's candidates are fixed.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path

import pandas as pd

from research.frozen_weekly import predictions, load_frozen
from research.model_epa_qbr_study import load_stats
from sunday_slate.data import load_schedules

STRATEGIES = (
    "Elo top 3 (unfiltered baseline)",
    "Elo top 5 (unfiltered baseline)",
    "Tier priority 1–3, maximum 5",
    "Strict Tier 1–2, maximum 5",
    "Tier 1–3 + challenger agreement",
    "Tier 1–2 plus stronger Tier 3",
)


def valid_number(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError, OverflowError):
        return None


def pregame_flags(row):
    """Fixed, mutually exclusive research categories using no future information."""
    conf = valid_number(row.get("pick_probability"))
    hp = valid_number(row.get("home_probability"))
    pp = valid_number(row.get("ppg_projected_margin"))
    challenger = valid_number(row.get("challenger_home_probability"))
    prior = valid_number(row.get("min_prior_games"))
    if conf is None or hp is None or not 0 <= conf <= 1 or not 0 <= hp <= 1:
        return None
    side = "home" if hp >= .5 else "away"
    ppg_agrees = (prior is not None and prior >= 3 and pp is not None
                  and abs(pp) > 1.e-9 and (pp > 0) == (side == "home"))
    challenger_agrees = (challenger is not None and 0 <= challenger <= 1
                         and (challenger >= .5) == (side == "home"))
    if conf >= .75:
        tier = 1
    elif conf >= .60 and ppg_agrees and abs(pp) >= 7:
        tier = 2
    elif conf >= .60 and ppg_agrees:
        tier = 3
    else:
        tier = 4
    return {"tier":tier, "confidence":conf, "ppg_agrees":ppg_agrees,
            "challenger_agrees":challenger_agrees, "ppg_margin":pp}


def ranked_candidates(week: pd.DataFrame, strategy: str) -> list[dict]:
    """Selection decisions use ONLY fixed pregame columns."""
    if strategy not in STRATEGIES:
        raise ValueError("Unrecognized strategy")
    out = []
    for row in week.to_dict("records"):
        flag = pregame_flags(row)
        if flag is None:
            continue
        tier = flag["tier"]
        if strategy.startswith("Tier priority") and tier >= 4:
            continue
        if strategy.startswith("Strict") and tier > 2:
            continue
        if strategy.endswith("challenger agreement") and (tier >= 4 or not flag["challenger_agrees"]):
            continue
        if strategy.startswith("Tier 1–2 plus stronger") and (
                tier >= 4 or (tier == 3 and
                              (flag["confidence"] < .65 or not flag["challenger_agrees"]
                               or abs(flag["ppg_margin"] or 0) < 3))):
            continue
        out.append({**row, **flag})
    # Most confident first within each category. We do not use scores/results
    # in ranking, even though a retrospective dataframe contains results.
    if strategy.startswith("Elo top"):
        out.sort(key=lambda r:(-r["confidence"], str(r["game_id"])))
    else:
        out.sort(key=lambda r:(r["tier"], -r["confidence"],
                               -abs(r["ppg_margin"] or 0), str(r["game_id"])))
    cap = 3 if "top 3" in strategy else 5
    return out[:cap]


def count_selected(rows):
    wins = sum(r["pick_result"] == "Correct" for r in rows)
    losses = sum(r["pick_result"] == "Incorrect" for r in rows)
    ties = len(rows)-wins-losses
    return {"games":len(rows),"wins":wins,"losses":losses,"ties":ties,
            "accuracy":round(100*wins/(wins+losses),1) if wins+losses else None}


def weekly_scores(games: pd.DataFrame, strategy: str) -> list[dict]:
    results = []
    for (season,week), frame in games.groupby(["season","week"],sort=True):
        if not frame["pick_result"].isin(["Correct","Incorrect","Push"]).all():
            # No partial-week grading/selection.
            continue
        chosen = ranked_candidates(frame,strategy)
        score = count_selected(chosen)
        score.update({"season":int(season),"week":int(week),
                      "game_ids":[str(r["game_id"]) for r in chosen],
                      "teams":[str(r["predicted_winner"]) for r in chosen],
                      "tiers":[r["tier"] for r in chosen]})
        results.append(score)
    return results


def summarize_weeks(weeks):
    n=len(weeks)
    selected=sum(x["games"] for x in weeks)
    wins=sum(x["wins"] for x in weeks)
    losses=sum(x["losses"] for x in weeks)
    ties=sum(x["ties"] for x in weeks)
    return {"weeks":n,"games":selected,"wins":wins,"losses":losses,
            "ties":ties,"accuracy":round(100*wins/(wins+losses),1) if wins+losses else None,
            "average_picks_per_week":round(selected/n,2) if n else None,
            "weeks_with_3_plus":sum(x["games"]>=3 for x in weeks),
            "weeks_with_3_to_5":sum(3<=x["games"]<=5 for x in weeks),
            "weeks_with_0_to_2":sum(x["games"]<3 for x in weeks),
            "weeks_perfect":sum(x["wins"]==x["games"] and x["games"]>0 for x in weeks),
            "weeks_3_plus_and_perfect":sum(x["wins"]==x["games"] and x["games"]>=3 for x in weeks)}


def build_report(preds):
    if preds.empty:
        raise ValueError("No pregame model predictions available")
    frame=preds[preds.season.isin([2023,2024,2025,2026])].copy()
    # Full weekly slates only; no completed games may be used from a partial week.
    full_weeks={(int(y),int(w)) for (y,w),g in frame.groupby(["season","week"])
                if g["pick_result"].isin(["Correct","Incorrect","Push"]).all()}
    frame=frame[frame.apply(lambda r:(int(r.season),int(r.week)) in full_weeks,axis=1)]
    baseline=count_selected([x for x in frame.to_dict("records") if x["pick_result"]!="Push"])
    results={}
    for strategy in STRATEGIES:
        weeks=weekly_scores(frame,strategy)
        by_season={str(year):summarize_weeks([x for x in weeks if x["season"]==year])
                   for year in [2023,2024,2025,2026]}
        results[strategy]={"retrospective_2023_2025":summarize_weeks(
                                [x for x in weeks if x["season"] in (2023,2024,2025)]),
                           "prospective_style_2026":by_season["2026"],
                           "years":by_season,
                           "weeks_2026":[x for x in weeks if x["season"]==2026],
                           "weekly_records_2023_2025":[x for x in weeks if x["season"]!=2026]}
    return {"status":"research-only; app Elo picks unchanged",
            "definition":"Straight-up winners, not ATS or betting profits.",
            "validation":"2023–2025 were previously inspected. This is retrospectively compared, not pristine holdout.",
            "freeze":"For any upcoming game, publish picks before the earliest kickoff and never retroactively replace them.",
            "baseline_full_slate":baseline,
            "strategies":results}


def markdown_report(report):
    lines=["# Sunday Slate | 3–5 game shortlist research","",
           "All shortlist selections are based on prior-week Elo, PPG consensus, and frozen research challenger forecasts, not on game outcomes or closing line movement.",
           "**Important:** these are *straight-up* winner rates, not evidence of ATS or moneyline profitability. Previously inspected seasons are retrospective, not untouched validation.","",
           "| Strategy | 2023–25 SU record | Accuracy | Picks/week | Weeks with 3+ | 2026 SU record |",
           "|---|---:|---:|---:|---:|---:|"]
    for name, data in report["strategies"].items():
        a=data["retrospective_2023_2025"]
        b=data["prospective_style_2026"]
        lines.append(f"| {name} | {a['wins']}–{a['losses']} | {a['accuracy']}% | "
                     f"{a['average_picks_per_week']} | {a['weeks_with_3_plus']}/{a['weeks']} | "
                     f"{b['wins']}–{b['losses']} ({b['accuracy']}%) |")
    lines.extend(["","## Decision rules",
                  "Heavy Favorite: Elo >=75%. Double Confirmation: Elo >=60%, prior games >=3, scoring model agrees with projected margin >=7. Solid Consensus: Elo >=60%, scoring model agrees, prior games >=3.",
                  "The ranker prioritizes stronger tiers, then Elo probabilities. Optional filters require frozen challenger agreement or tighter Tier 3 confirmation.",
                  "Do not promote a strategy simply because it looks best on this inspected sample. Use one fixed strategy on future weeks and score it without changing its rules.",
                  "Do not force three picks in weeks lacking three qualifying candidates. Do not use sportsbook closing lines, opening-to-closing changes, or other retrospective-only info to predict past games.",
                  "The high-confidence SU candidates may have very poor betting payout. Moneyline value, ATS and closing-line value require separate historical timestamped price validation.",""])
    return "\n".join(lines)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default="research/output/weekly_shortlist_results.json")
    args=parser.parse_args()
    schedule=load_schedules()
    stats=load_stats()
    data=predictions(schedule,stats,load_frozen())
    report=build_report(data)
    path=Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    path.with_suffix(".md").write_text(markdown_report(report)+"\n")
    print(markdown_report(report),flush=True)


if __name__=="__main__":
    main()

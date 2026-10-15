"""Explore additions to Sunday's 3–5-game shortlist without changing deployed picks.

All screens use prior-week information. Historical picks are reconstructed,
not honestly prospective market bets; season 2023–25 is multiply inspected.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path

import pandas as pd

from research.frozen_weekly import predictions, load_frozen
from research.model_epa_qbr_study import load_stats
from research.run_defense_rush import load_rush_stats, _snapshot, _selection
from research.weekly_shortlist import ranked_candidates, pregame_flags, count_selected, summarize_weeks
from sunday_slate.coach_ats import coach_history
from sunday_slate.data import load_schedules

ROOT = Path("research/output")
CORE = "Tier 1–2 plus stronger Tier 3"
STRATEGIES = [
    "Loose PPG + challenger",
    "Strong Elo + challenger",
    "Strong Elo only",
    "Rush support + challenger",
    "Coach venue ATS support",
    "PPG or rushing support + challenger",
]
RULE_DESCRIPTION = {
    "Loose PPG + challenger":"Elo >=60%, challenger agrees, PPG on same side >=1.0, 3+ prior games",
    "Strong Elo + challenger":"Elo >=68%, challenger agrees, no additional PPG threshold",
    "Strong Elo only":"Elo >=68% (select next-highest Elo confidence)",
    "Rush support + challenger":"Elo >=60%, challenger agrees and 25th-percentile rushing mismatch backs Elo",
    "Coach venue ATS support":"Elo >=60%, 10+ past decisions per coach venue, model side >=58% ATS, opponent <=45% ATS, >=15 percentage-point gap",
    "PPG or rushing support + challenger":"Elo >=60%, challenger agrees, either PPG agrees >=1 or rushing mismatch agrees",
}


def rushing_flags(games: pd.DataFrame, team_stats: pd.DataFrame) -> dict:
    """Rushing metric based on past within-season games only, computed before any weekly result."""
    flags={}
    games=games[games.game_type.eq("REG") & games.season.isin([2023,2024,2025,2026])]
    games=games.sort_values(["season","week","game_id"])
    stats=team_stats.set_index(["game_id","team"],drop=False)
    if stats.index.duplicated().any():
        raise ValueError("Duplicate weekly rushing teams")
    for season, season_games in games.groupby("season",sort=True):
        state=defaultdict(lambda:{"games":0,"rush_yards":0.,"carries":0.,"opp_rush_yards":0.,"opp_carries":0.})
        for week, slate in season_games.groupby("week",sort=True):
            ranked, offensive, defensive=_snapshot(state,3)
            if len(ranked)>=10:
                weak=float(pd.Series(offensive).quantile(.25))
                strong=float(pd.Series(defensive).quantile(.25))
                for g in slate.to_dict("records"):
                    candidate=_selection(str(g["home_team"]),str(g["away_team"]),ranked,weak,strong)
                    if candidate:
                        flags[str(g["game_id"])]=candidate
            # Scores in this week cannot affect this week's flagged matchups.
            for g in slate.to_dict("records"):
                if pd.isna(g["home_score"]) or pd.isna(g["away_score"]):
                    continue
                h,a=str(g["home_team"]),str(g["away_team"])
                k=(str(g["game_id"]),h)
                l=(str(g["game_id"]),a)
                if k not in stats.index or l not in stats.index:
                    continue
                hr,ar=stats.loc[k],stats.loc[l]
                if (str(hr["opponent_team"])!=a or str(ar["opponent_team"])!=h
                        or int(hr["week"])!=int(week) or int(ar["week"])!=int(week)):
                    continue
                for team,own,opp in ((h,hr,ar),(a,ar,hr)):
                    s=state[team]
                    s["games"]+=1
                    s["rush_yards"]+=float(own["rushing_yards"])
                    s["carries"]+=float(own["carries"])
                    s["opp_rush_yards"]+=float(opp["rushing_yards"])
                    s["opp_carries"]+=float(opp["carries"])
    return flags


def coach_flags(games: pd.DataFrame) -> dict:
    """Prior-date venue ATS only. Current spread role is NOT inferred from final lines."""
    history=coach_history(games)
    flags={}
    source=games[games.game_type.eq("REG") & games.season.isin([2023,2024,2025,2026])]
    for (season,week),slate in source.groupby(["season","week"],sort=True):
        # Exclude full target week so Thursday/Sunday earlier results cannot sneak in.
        earliest=pd.to_datetime(slate["gameday"],utc=True,errors="coerce").min()
        past=history[history.day < earliest]
        for g in slate.to_dict("records"):
            if str(g.get("location","")).casefold() != "home":
                continue
            splits={}
            for side,venue in (("home","Home"),("away","Road")):
                coach=g.get(side+"_coach")
                if not isinstance(coach,str) or not coach.strip():
                    break
                relevant=past[(past.coach==coach.strip().casefold()) & (past.venue==venue)]
                graded=relevant[relevant.result.isin(["W","L"])]
                if len(graded)<10:
                    break
                pct=graded.result.eq("W").mean()*100
                splits[side]={"pct":round(float(pct),2),"games":len(graded)}
            if len(splits)==2:
                better="home" if splits["home"]["pct"]>splits["away"]["pct"] else "away"
                candidate=str(g[better+"_team"])
                flags[str(g["game_id"])]={
                    "team":candidate,"team_pct":splits[better]["pct"],
                    "opponent_pct":splits["away" if better=="home" else "home"]["pct"],
                    "gap":abs(splits["home"]["pct"]-splits["away"]["pct"]),
                    "team_n":splits[better]["games"],
                    "opponent_n":splits["away" if better=="home" else "home"]["games"],
                }
    return flags


def eligible(row,kind,rush,coach):
    flag=pregame_flags(row)
    if flag is None: return False
    p=flag["confidence"]
    pp=flag["ppg_margin"]
    ppg_ok=(flag["ppg_agrees"] and pp is not None and abs(pp)>=1)
    challenge=flag["challenger_agrees"]
    rush_ok=rush.get(str(row["game_id"]))==str(row["predicted_winner"])
    hist=coach.get(str(row["game_id"]),{})
    coach_ok=(hist.get("team")==str(row["predicted_winner"])
              and hist.get("team_pct",0)>=58 and hist.get("opponent_pct",100)<=45
              and hist.get("gap",0)>=15)
    return {
        STRATEGIES[0]: p>=.60 and challenge and ppg_ok,
        STRATEGIES[1]: p>=.68 and challenge,
        STRATEGIES[2]: p>=.68,
        STRATEGIES[3]: p>=.60 and challenge and rush_ok,
        STRATEGIES[4]: p>=.60 and coach_ok,
        STRATEGIES[5]: p>=.60 and challenge and (ppg_ok or rush_ok),
    }[kind]


def select_week(frame,kind,rush,coach,target):
    """Never modify the established core; append only until a target cap of 3 or 5."""
    base=ranked_candidates(frame, CORE)
    assert len(base)<=5
    used={str(r["game_id"]) for r in base}
    addons=[]
    for row in frame.to_dict("records"):
        if str(row["game_id"]) in used:continue
        if not eligible(row,kind,rush,coach):continue
        flag=pregame_flags(row)
        addons.append({**row,**flag})
    addons.sort(key=lambda r:(-r["confidence"],str(r["game_id"])))
    spots=max(0,target-len(base))
    chosen=base+addons[:spots]
    return chosen,addons[:spots],addons


def score_all(preds, schedule, rush,coach):
    frame=preds[preds.season.isin([2023,2024,2025,2026])].copy()
    groups=[]
    for (season,week),slate in frame.groupby(["season","week"],sort=True):
        if slate["pick_result"].isin(["Correct","Incorrect","Push"]).all():
            groups.append((int(season),int(week),slate))
    data={}
    for kind in STRATEGIES:
        variants={}
        for target in (3,5):
            weeks=[];extra_rows=[];missing_rows=[]
            for season,week,slate in groups:
                selected,added,all_candidates=select_week(slate,kind,rush,coach,target)
                score=count_selected(selected)
                score.update({"season":season,"week":week,"core_count":len(ranked_candidates(slate,CORE)),
                              "extras":len(added),"available_addons":len(all_candidates),
                              "picks":[{"game_id":str(row["game_id"]),"selected":str(row["predicted_winner"]),
                                        "home":str(row["home_team"]),"away":str(row["away_team"]),
                                        "elo":round(float(row["pick_probability"]),4),
                                        "tier":int(row["tier"]),"ppg":row["ppg_margin"],
                                        "reason":"Core" if i < score["games"]-len(added) else kind,
                                        "outcome":"W" if row["pick_result"]=="Correct" else
                                        "L" if row["pick_result"]=="Incorrect" else "T"}
                                       for i,row in enumerate(selected)]})
                weeks.append(score)
                for row in added:
                    extra_rows.append({"season":season,"week":week,
                        "game_id":str(row["game_id"]),"team":str(row["predicted_winner"]),
                        "tier":int(row["tier"]),"confidence":round(float(row["confidence"]),4),
                        "ppg_margin":row["ppg_margin"],
                        "rush_agrees":rush.get(str(row["game_id"]))==str(row["predicted_winner"]),
                        "coach_agrees":coach.get(str(row["game_id"]),{}).get("team")==str(row["predicted_winner"]),
                        "result":row["pick_result"],"outcome": "W" if row["pick_result"]=="Correct" else "L" if row["pick_result"]=="Incorrect" else "T"})
            def summarize(period):
                series=[r for r in weeks if r["season"] in period]
                extras=[r for r in extra_rows if r["season"] in period]
                return {**summarize_weeks(series),"additions":count_selected(
                    [{"pick_result":r["result"]} for r in extras]),
                    "added_by_season":{str(y):count_selected(
                        [{"pick_result":r["result"]} for r in extras if r["season"]==y])
                        for y in period}}
            variants[str(target)]={"historical_2023_2025":summarize([2023,2024,2025]),
                                   "preliminary_2026":summarize([2026]),
                                   "weeks_2026":[r for r in weeks if r["season"]==2026],
                                   "additions_2026":[r for r in extra_rows if r["season"]==2026],
                                   "weekly_2023_2025":[{"season":r["season"],"week":r["week"],
                                    "games":r["games"],"wins":r["wins"],"losses":r["losses"],
                                    "extras":r["extras"]} for r in weeks if r["season"]!=2026]}
        data[kind]=variants
    return {"status":"RESEARCH_ONLY; never changes the app or the frozen Week 6 archive",
            "rules":RULE_DESCRIPTION,"retrospective_warning":"Rules reviewed using previously examined 2023–25 seasons. PPG/Elo/challenger features prior week, but not untouched out-of-sample predictions.",
            "controls":"Frozen original core picks remain unchanged. Compare top-up-to-3 and top-up-to-5 against baseline. No odds-based flags are used.",
            "strategies":data}


def render(results):
    lines=["# Sunday Slate near-miss investigation","",
           "Same frozen core eligibility. Optional supplements are placed only AFTER existing core picks, never replacing them.",
           "Decisions use preweek Elo, PPG, prior rushing YPC, or prior venue head-coach ATS records. Never use the target game's outcome, the target game's closing line, or later-week stats.","",
           "| Extra-selection rule | Target | 2023–25 SU | Added-only SU | Weeks >=3 | 2026 SU | 2026 added-only |",
           "|---|---:|---|---|---|---|---|"]
    for name,cases in results["strategies"].items():
        for target,rec in cases.items():
            h,p=rec["historical_2023_2025"],rec["preliminary_2026"]
            a,b=h["additions"],p["additions"]
            lines.append(f"| {name} | {target} | {h['wins']}-{h['losses']} ({h['accuracy']}%) | "
                         f"{a['wins']}-{a['losses']} ({a['accuracy']}%) | "
                         f"{h['weeks_with_3_plus']}/{h['weeks']} | {p['wins']}-{p['losses']} ({p['accuracy']}%) | "
                         f"{b['wins']}-{b['losses']} ({b['accuracy']}%) |")
    lines.extend(["","## 2026 added games (target 3)"])
    for name, cases in results["strategies"].items():
        lines.extend(["","### "+name])
        rec=cases["3"]
        for week in rec["weeks_2026"]:
            additions=[p for p in week["picks"] if p["reason"]!="Core"]
            txt=", ".join(f"{p['selected']} {p['outcome']} ({p['elo']:.1%})" for p in additions) or "None"
            lines.append(f"- Week {week['week']}: core {week['core_count']} + {len(additions)}; additions {txt}")
    lines.extend(["","## Limitations",
                  "Previous weeks are retrospective; selecting the best-looking variant after inspecting outcomes is multiple-testing overfit.",
                  "Historical coach ATS uses prior NFLverse reference spreads, not verified sportsbook-specific prices; no current-matchup closing line enters a signal.",
                  "Rushing YPC is not opponent-adjusted EPA; previous research found it inferior to Elo as an independent picker.",
                  "Early-season gaps may remain because the data-driven candidate signals require prior games. Do not fill the slate by force.",
                  "This is straight-up prediction grading, not ATS or moneyline return."])
    return "\n".join(lines)+"\n"


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default="research/output/shortlist_nearmisses.json")
    args=ap.parse_args()
    print("Loading schedules and preweek NFL team stats",flush=True)
    schedule=load_schedules()
    stats=load_stats()
    predictions_frame=predictions(schedule,stats,load_frozen())
    print("Computing preweek rushing signals",flush=True)
    rush=rushing_flags(schedule,load_rush_stats())
    print("Computing prior venue coaching records",flush=True)
    coaches=coach_flags(schedule)
    report=score_all(predictions_frame,schedule,rush,coaches)
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    output.with_suffix(".md").write_text(render(report))
    print(render(report),flush=True)


if __name__=="__main__":
    main()

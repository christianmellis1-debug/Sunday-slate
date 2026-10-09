"""Rushing success rate + opponent-adjusted rushing EPA NFL hypothesis study.

Definitions locked before evaluating 2023–2025:
* Designed rush, no QB scramble/kneel, quarters 1-3, pre-play absolute score
  differential <=14, valid down & distance and finite EPA.
* Conventional down-distance success: >=40% yards-to-go on 1st, 60% on 2nd,
  >=100% on 3rd/4th. This is NOT nflverse's EPA-positive success field.
* Fit a weighted, ridge-shrunk two-way EPA/carry model on ALL available prior
  neutral-script game rush lines: EPA = league mean + offense + defense allowed.
  Each coefficient is regularized with the equivalent of 150 rush attempts;
  no plays in current or future weeks enter an earlier rating.
* At least 3 previously completed regular-season games for BOTH teams.
* Strong run defense = lower quartile of opponent rushing success allowed OR
  opponent-adjusted rushing EPA allowed. Weak rushing offense = lower
  quartile of rushing success OR opponent-adjusted offensive EPA.
* Study separately and combined; exclude ambiguous both-sides qualify games.
* 2019–2022 discovery and 2023–2025 untouched evaluation, 2026 separate.
* Straight-up and closing reference ATS against frozen NFL-ELO-1.0.

Run: python -m research.run_rush_success_adjusted --output rush_adjusted_results.json
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from research.test_qbr_defense import load_games
from sunday_slate.model import predict_regular_season

TRAIN = (2019, 2020, 2021, 2022)
TEST = (2023, 2024, 2025)
CURRENT = (2026,)
YEARS = TRAIN + TEST + CURRENT
MIN_GAMES = 3
RIDGE_EQUIV_PLAYS = 150.0
THRESHOLDS = (0.20, 0.25, 1/3, 0.40)
REQUIRED = {"season", "week", "game_id", "posteam", "defteam",
            "rush_attempt", "qb_scramble", "qb_kneel", "qtr",
            "score_differential", "epa", "down", "ydstogo",
            "yards_gained", "play_type", "season_type"}


def load_aggregates(pinned: str | None = None) -> pd.DataFrame:
    """Data frame containing one record per completed-game offense and defense."""
    if pinned:
        return _validate_aggregates(pd.read_csv(pinned, low_memory=False))
    import nflreadpy
    import polars as pl
    all_seasons = []
    for season in YEARS:
        raw = nflreadpy.load_pbp(seasons=[int(season)])
        missing = REQUIRED - set(raw.columns)
        if missing:
            raise ValueError(f"PBP data for {season} missing {sorted(missing)}")
        data = raw.select(sorted(REQUIRED)).filter(
            (pl.col("season_type") == "REG") &
            (pl.col("play_type") == "run") &
            (pl.col("rush_attempt") == 1) &
            (pl.col("qb_scramble") == 0) &
            (pl.col("qb_kneel") == 0) &
            (pl.col("qtr").is_between(1, 3)) &
            (pl.col("score_differential").abs() <= 14) &
            (pl.col("down").is_between(1, 4)) &
            (pl.col("ydstogo") > 0) &
            (pl.col("epa").is_not_null()) &
            (pl.col("yards_gained").is_not_null()) &
            (pl.col("posteam").is_not_null()) &
            (pl.col("defteam").is_not_null())
        )
        df = pd.DataFrame(data.to_dicts())
        if df.empty:
            raise ValueError(f"No eligible rushing plays in {season}")
        for col in ("season","week","epa","down","ydstogo","yards_gained"):
            df[col] = pd.to_numeric(df[col],errors="coerce")
        df=df.dropna(subset=["epa","down","ydstogo","yards_gained"])
        df=df[np.isfinite(df["epa"]) & df["ydstogo"].gt(0) & df["down"].between(1,4)].copy()
        target = np.select(
            [df["down"].eq(1),df["down"].eq(2)],
            [0.4*df["ydstogo"],0.6*df["ydstogo"]],
            default=df["ydstogo"]
        )
        df["sr_success"] = df["yards_gained"].ge(target).astype(float)
        agg=df.groupby(["season","week","game_id","posteam","defteam"],as_index=False).agg(
            n=("epa","size"),rush_epa_sum=("epa","sum"),
            successes=("sr_success","sum"),
        )
        all_seasons.append(agg)
        print(f"YEAR {season}: {len(df)} neutral-script rushes, {len(agg)} team-games",flush=True)
    frame=pd.concat(all_seasons,ignore_index=True)
    return _validate_aggregates(frame)


def _validate_aggregates(df: pd.DataFrame) -> pd.DataFrame:
    needed = {"season","week","game_id","posteam","defteam","n","rush_epa_sum","successes"}
    if not needed.issubset(df):
        raise ValueError(f"Rush aggregates missing {sorted(needed - set(df))}")
    frame=df.copy()
    for col in ("season","week","n","rush_epa_sum","successes"):
        frame[col]=pd.to_numeric(frame[col],errors="coerce")
    if frame[["season","week","n","rush_epa_sum","successes"]].isna().any().any():
        raise ValueError("Invalid missing numeric rush aggregate value")
    if (frame["n"]<=0).any() or (frame["successes"]<0).any() or (frame["successes"]>frame["n"]).any():
        raise ValueError("Impossible per-game success rates or rush counts")
    if frame.duplicated(["game_id","posteam"]).any():
        raise ValueError("Duplicate offense team/game lines")
    return frame


def adjusted_ratings(history: list[dict], eligible_teams: set[str]) -> dict[str, dict]:
    """Earlier-week ridge regression with offense and opponent defense effects.

    Observations: each historical game-team aggregate, weighted by its count of
    designed rush plays. Symmetric ridge shrinkage + baseline intercept.
    Sign of defensive rating: LOWER = better defense (less allowed EPA).
    """
    teams = sorted(eligible_teams)
    if not teams or not history:
        return {}
    pos={t:i for i,t in enumerate(teams)}
    nteams=len(teams)
    rows=[r for r in history if r["posteam"] in pos and r["defteam"] in pos]
    if len(rows)<10:
        return {}
    X=np.zeros((len(rows),1+2*nteams),dtype=float)
    y=np.zeros(len(rows),dtype=float)
    weights=np.zeros(len(rows),dtype=float)
    for i,r in enumerate(rows):
        X[i,0]=1.
        X[i,1+pos[r["posteam"]]]=1.
        X[i,1+nteams+pos[r["defteam"]]]=1.
        y[i]=r["rush_epa_sum"]/r["n"]
        weights[i]=float(r["n"])
    normal=(X.T*weights)@X
    rhs=X.T@(weights*y)
    penalty=np.eye(normal.shape[0])*RIDGE_EQUIV_PLAYS
    penalty[0,0]=0.
    coefs=np.linalg.solve(normal+penalty,rhs)
    return {t: {"off":float(coefs[1+i]),"def":float(coefs[1+nteams+i])}
            for t,i in pos.items()}


def _quantile_cutoffs(values: dict, q: float, offense_key: str, defense_key: str):
    return (float(np.quantile([d[offense_key] for d in values.values()],q)),
            float(np.quantile([d[defense_key] for d in values.values()],q)))


def _candidate(home: str, away: str, metrics: dict, offense_key: str, defense_key: str,
               cutoff_off: float, cutoff_def: float) -> str | None:
    if home not in metrics or away not in metrics:
        return None
    h=metrics[home][defense_key]<=cutoff_def and metrics[away][offense_key]<=cutoff_off
    a=metrics[away][defense_key]<=cutoff_def and metrics[home][offense_key]<=cutoff_off
    return home if h and not a else away if a and not h else None


def run_study(games: pd.DataFrame, aggregates: pd.DataFrame, min_games: int = MIN_GAMES) -> pd.DataFrame:
    """Predict using only games from earlier weeks. Never consult same-week outcomes."""
    frame=games[games.season.isin(YEARS)].sort_values(["season","week","game_id"])
    box=aggregates.set_index(["game_id","posteam"])
    elo=predict_regular_season(games).set_index("game_id")[["predicted_winner","pick_probability"]]
    emitted=[]
    coverage={"completed_games":0,"paired_rush_games":0,"neutral_script_team_games":len(aggregates)}
    for season, season_games in frame.groupby("season",sort=True):
        past=[]
        counts=defaultdict(int)
        rush=defaultdict(lambda:{"n":0.,"successes":0.,"opp_n":0.,"opp_successes":0.})
        for week, slate in season_games.groupby("week",sort=True):
            eligible={team for team,num in counts.items() if num>=min_games}
            raw_metrics={}
            for team in eligible:
                d=rush[team]
                if d["n"]>0 and d["opp_n"]>0:
                    raw_metrics[team]={"off":d["successes"]/d["n"],
                                       "def":d["opp_successes"]/d["opp_n"]}
            # Opponent adjustment is entirely based on prior weeks.
            adjusted=adjusted_ratings(past,set(raw_metrics))
            metrics={
                "success":raw_metrics,
                "adj_epa":adjusted,
            }
            for g in slate.to_dict("records"):
                hs,aw=g["home_score"],g["away_score"]
                if pd.isna(hs) or pd.isna(aw) or hs==aw:
                    continue
                coverage["completed_games"]+=1
                home,away=g["home_team"],g["away_team"]
                winner=home if hs>aw else away
                if g["game_id"] not in elo.index:
                    raise ValueError(f"Elo missing {g['game_id']}")
                frozen=elo.loc[g["game_id"]]
                ats_line=pd.to_numeric(g.get("spread_line"),errors="coerce")
                margin=float(hs-aw)
                for q in THRESHOLDS:
                    selected={}
                    for kind,context in metrics.items():
                        if len(context)<10:
                            selected[kind]=None
                            continue
                        cut_off,cut_def=_quantile_cutoffs(context,q,"off","def")
                        selected[kind]=_candidate(home,away,context,"off","def",cut_off,cut_def)
                    selected["combined"]=(
                        selected["success"] if selected["success"] is not None
                        and selected["success"]==selected["adj_epa"] else None)
                    for kind,choice in selected.items():
                        if choice is None:
                            continue
                        ats=None
                        if pd.notna(ats_line):
                            diff=margin-float(ats_line)
                            if abs(diff)>1e-8:
                                ats=(diff>0) if choice==home else (diff<0)
                        emitted.append({
                            "season":int(season),"week":int(week),"game_id":g["game_id"],
                            "metric":kind,"quantile":round(q,6),"signal_team":choice,
                            "winner":winner,"elo_team":frozen["predicted_winner"],
                            "cover":ats,
                            "elo_probability":float(frozen["pick_probability"]),
                        })
            # Only AFTER entire slate graded do completed past rush games enter history.
            for g in slate.to_dict("records"):
                if pd.isna(g["home_score"]) or pd.isna(g["away_score"]):
                    continue
                home,away=g["home_team"],g["away_team"]
                if (g["game_id"],home) not in box.index or (g["game_id"],away) not in box.index:
                    continue
                h=box.loc[(g["game_id"],home)]
                a=box.loc[(g["game_id"],away)]
                if (str(h["defteam"])!=away or str(a["defteam"])!=home
                        or int(h["season"])!=int(season) or int(a["season"])!=int(season)
                        or int(h["week"])!=int(week) or int(a["week"])!=int(week)):
                    raise ValueError(f"Rush input mismatches schedule for {g['game_id']}")
                coverage["paired_rush_games"]+=1
                for team,own,opp in ((home,h,a),(away,a,h)):
                    counts[team]+=1
                    rush[team]["n"]+=float(own["n"])
                    rush[team]["successes"]+=float(own["successes"])
                    rush[team]["opp_n"]+=float(opp["n"])
                    rush[team]["opp_successes"]+=float(opp["successes"])
                    past.append({"posteam":team,"defteam":str(own["defteam"]),
                                 "n":float(own["n"]),"rush_epa_sum":float(own["rush_epa_sum"])})
    output=pd.DataFrame(emitted)
    output.attrs["coverage"]=coverage
    return output


def grade(data: pd.DataFrame) -> dict:
    n=len(data)
    wins=int(data.signal_team.eq(data.winner).sum())
    baseline=int(data.elo_team.eq(data.winner).sum())
    conflict=data[data.signal_team.ne(data.elo_team)]
    c_n=len(conflict)
    signal_c=int(conflict.signal_team.eq(conflict.winner).sum())
    graded=data[data.cover.notna()]
    ats_n=len(graded);ats_w=int(graded.cover.eq(True).sum())
    return {
        "signal":{"games":n,"wins":wins,"losses":n-wins,"pct":round(100*wins/n,2) if n else None},
        "elo_same_games":{"games":n,"wins":baseline,"losses":n-baseline,"pct":round(100*baseline/n,2) if n else None},
        "against_elo":{"games":c_n,"signal_wins":signal_c,"elo_wins":c_n-signal_c,"net_changed_correct":2*signal_c-c_n},
        "historical_spread":{"games":ats_n,"covers":ats_w,"noncovers":ats_n-ats_w,"pct":round(100*ats_w/ats_n,2) if ats_n else None,"excluded_pushes_missing":n-ats_n},
    }


def report(frame: pd.DataFrame, years: tuple[int,...]) -> dict:
    data=frame[frame.season.isin(years)]
    return {
        f"{kind}_{q:.6f}":grade(data[data["metric"].eq(kind) & data["quantile"].eq(round(q,6))])
        for kind in ("success","adj_epa","combined") for q in THRESHOLDS
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--games",help="Pinned nfldata schedule CSV")
    parser.add_argument("--aggregates",help="Pinned play-by-play neutral script rushing summary CSV")
    parser.add_argument("--output")
    options=parser.parse_args()
    games=load_games(options.games)
    aggregates=load_aggregates(options.aggregates)
    print("INPUT_MATCHED_NEUTRAL_RUSH_TEAM_GAMES",len(aggregates),flush=True)
    predictions=run_study(games,aggregates)
    if predictions.empty:
        raise ValueError("Zero eligible research games")
    result={
        "definition":"Designed rushes (non kneel, non scramble) quarters 1-3, preplay score margin <=14; successes 40/60/100% yards-to-go by down. EPA opponent adjusted by ridge regression, offense + defense effects weighted per game neutral rush attempts, shrinkage equivalent 150 plays. Each weekly model fitted only with earlier completed games.",
        "sources":"nflverse play-by-play released via nflreadpy.load_pbp, NFLverse games/closing spread_line. Market lines have no certified pregame timestamp.",
        "discovery_years":list(TRAIN),"holdout_years":list(TEST),"2026_ytd_years":list(CURRENT),
        "coverage":predictions.attrs["coverage"],
        "discovery_2019_2022":report(predictions,TRAIN),
        "holdout_2023_2025":report(predictions,TEST),
        "diagnostic_2026_ytd":report(predictions,CURRENT),
        "by_year_at_primary_25pct": {
            str(year): {
                kind:grade(predictions[
                    predictions["season"].eq(year) &
                    predictions["metric"].eq(kind) &
                    predictions["quantile"].eq(.25)
                ]) for kind in ("success", "adj_epa", "combined")
            } for year in TRAIN + TEST + CURRENT
        },
        "decision":"No prediction engine change unless reproducible gains against Elo and season-robust independently timestamped ATS evidence.",
    }
    print("SUCCESS_ADJUSTED_JSON_BEGIN\n"+json.dumps(result,indent=2,allow_nan=False)+"\nSUCCESS_ADJUSTED_JSON_END",flush=True)
    if options.output:
        Path(options.output).write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    if options.aggregates is None:
        # Save deterministic short derived data to enable future independent reruns.
        aggregates.to_csv("neutral_rushing_game_aggregates.csv",index=False)


if __name__=="__main__":
    main()

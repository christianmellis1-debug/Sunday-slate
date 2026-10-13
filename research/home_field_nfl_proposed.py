"""Research-only NFL port of Saturday Forecast Home Field Advantage, 2026-10-12.

Historical closing lines are retrospective reference quotes, NOT executable prices.
No production predictor files are touched. All team features are from earlier weeks.
"""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sunday_slate.model import predict_regular_season

WEIGHTS = np.array([.40, .25, .15, .10, .10])
REQUIRED = ["season", "week", "game_id", "team", "opponent_team",
            "season_type", "passing_epa", "rushing_epa", "attempts",
            "carries", "rushing_yards", "completions", "passing_interceptions",
            "fumbles_lost_total", "passing_20", "rushing_10"]
TRAIN, TEST, CURRENT = (2019,2020,2021,2022), (2023,2024,2025), (2026,)
YEARS = TRAIN + TEST + CURRENT

def team_vector(row):
    """Nine additive offense totals; share them as opponent-allowed for defense."""
    vals = [row["passing_epa"] + row["rushing_epa"],
            row["attempts"] + row["carries"],
            row["rushing_yards"], row["carries"],
            row["completions"], row["attempts"],
            row["passing_interceptions"] + row["fumbles_lost_total"],
            row["passing_20"] + row["rushing_10"], 1.]
    arr = np.asarray(vals, dtype=float)
    if not np.isfinite(arr).all() or min(arr[1],arr[3],arr[5]) <= 0:
        return None
    return arr

def features(games, stat_rows, year, week):
    """Build complete two-sided prior-game snapshots; do not invent missing boxes."""
    past = games[(games.season.eq(year)) & (games.week.lt(week)) &
                 games.home_score.notna() & games.away_score.notna()]
    expected = {}
    paired = {}
    for g in past.itertuples():
        for t in (g.home_team, g.away_team):
            expected[t] = expected.get(t, 0) + 1
        keyh = (g.game_id, g.home_team)
        keya = (g.game_id, g.away_team)
        if keyh not in stat_rows or keya not in stat_rows:
            continue
        h,a = stat_rows[keyh],stat_rows[keya]
        if (str(h["opponent_team"]) != g.away_team or
            str(a["opponent_team"]) != g.home_team or
            int(h["week"]) != int(g.week) or int(a["week"]) != int(g.week)):
            continue
        hv,av = team_vector(h), team_vector(a)
        if hv is None or av is None: continue
        for t, own, other in ((g.home_team,hv,av),(g.away_team,av,hv)):
            if t not in paired: paired[t] = [np.zeros(9),np.zeros(9)]
            paired[t][0] += own
            paired[t][1] += other

    values={}
    for team,(own,opp) in paired.items():
        if own[8] < 3 or own[8] != expected[team] or opp[8] != own[8]:
            continue
        if min(own[1],own[3],own[5],opp[1],opp[3],opp[5]) <= 0:
            continue
        offense = [own[0]/own[1],own[2]/own[3],own[4]/own[5],
                   own[6]/own[8],own[7]/own[1]]
        defense = [opp[0]/opp[1],opp[2]/opp[3],opp[4]/opp[5],
                   opp[6]/opp[8],opp[7]/opp[1]]
        values[team] = np.array([offense,defense],dtype=float)
    if len(values) < 16:
        return {}
    teams=list(values)
    raw=np.stack(list(values.values()))
    oriented=raw * np.array([[1,1,1,-1,1],[-1,-1,-1,1,-1]])
    mu=oriented.mean(axis=0)
    sd=oriented.std(axis=0)
    if (sd < 1e-10).any() or not np.isfinite(sd).all():
        return {}
    z=(oriented-mu)/sd
    profiles=np.sum(z*WEIGHTS,axis=2)
    return dict(zip(teams,profiles))

def read_inputs():
    import nflreadpy
    games=pd.DataFrame(nflreadpy.load_schedules(seasons=True).to_dicts())
    stats=pd.DataFrame(nflreadpy.load_team_stats(
        seasons=list(YEARS),summary_level="week").to_dicts())
    missing=set(REQUIRED)-set(stats.columns)
    if missing: raise ValueError("Missing team stats: "+", ".join(sorted(missing)))
    print("STATS ROWS BY SEASON:",stats.groupby("season").size().to_dict(),flush=True)
    stats=stats[stats.season_type.eq("REG") & stats.season.isin(YEARS)].copy()
    stats=stats.replace([np.inf,-np.inf],np.nan)
    for c in (set(REQUIRED)-{"game_id","team","opponent_team","season_type"}):
        stats[c]=pd.to_numeric(stats[c],errors="coerce")
    valid=stats[REQUIRED].notna().all(axis=1)
    stats=stats.loc[valid].copy()
    if stats.duplicated(["game_id","team"]).any():
        raise ValueError("Duplicate weekly team/game observations")
    games=games[games.game_type.eq("REG")].copy()
    games["season"]=pd.to_numeric(games.season,errors="coerce")
    games["week"]=pd.to_numeric(games.week,errors="coerce")
    for c in ("home_score","away_score","home_moneyline","away_moneyline","spread_line"):
        games[c]=pd.to_numeric(games[c],errors="coerce")
    if games.game_id.duplicated().any():
        raise ValueError("Duplicated schedule game IDs")
    return games,stats

def bucket(v):
    if v<.25: return "0.00-0.24"
    if v<.50: return "0.25-0.49"
    if v<.75: return "0.50-0.74"
    if v<1.00: return "0.75-0.99"
    if v<1.50: return "1.00-1.49"
    return "1.50+"

def rate(rows):
    n=len(rows)
    w=sum(r["win"] for r in rows)
    ep=sum(r["elo_correct"] for r in rows)
    ats=[r["ats_cover"] for r in rows if r["ats_cover"] is not None]
    ml=[r["reference_profit"] for r in rows if r["reference_profit"] is not None]
    return {"games":n,"su_wins":w,"su_losses":n-w,
            "su_pct":round(w/n*100,2) if n else None,
            "elo_wins_same_games":ep,"elo_losses_same_games":n-ep,
            "elo_pct_same_games":round(ep/n*100,2) if n else None,
            "ats_wins":sum(ats),"ats_losses":len(ats)-sum(ats),
            "ats_pct":round(sum(ats)/len(ats)*100,2) if ats else None,
            "ats_graded":len(ats),"ml_bets":len(ml),
            "ml_profit_units":round(sum(ml),3),"ml_roi_pct":round(sum(ml)/len(ml)*100,2) if ml else None}

def run(games,stats):
    keyed={(r.game_id,r.team):r._asdict() for r in stats.itertuples(index=False)}
    elo=predict_regular_season(games).set_index("game_id")
    records=[]
    audits={"eligible_dual_edge":0,"home_favorites":0,"missing_pregame_stats":0,
            "missing_market":0,"rejected_neutral":0}
    for year in YEARS:
        yr=games[games.season.eq(year)].sort_values(["week","game_id"])
        for week,slate in yr.groupby("week",sort=True):
            pre=features(games,keyed,year,int(week))
            for g in slate.itertuples():
                if pd.isna(g.home_score) or pd.isna(g.away_score) or g.home_score==g.away_score:
                    continue
                if "neutral" in str(g.location).lower():
                    audits["rejected_neutral"]+=1
                    continue
                if g.home_team not in pre or g.away_team not in pre:
                    audits["missing_pregame_stats"]+=1
                    continue
                ho,hd=pre[g.home_team]; ao,ad=pre[g.away_team]
                edge_off, edge_def=float(ho-ao),float(hd-ad)
                if edge_off<=1e-10 or edge_def<=1e-10:
                    continue
                audits["eligible_dual_edge"]+=1
                hml,aml=g.home_moneyline,g.away_moneyline
                if pd.isna(hml) or pd.isna(aml):
                    audits["missing_market"]+=1
                    continue
                if not (-500<hml<=-100 and aml>0):
                    continue
                audits["home_favorites"]+=1
                if g.game_id not in elo.index: raise ValueError("Elo mismatch")
                margin=float(g.home_score-g.away_score)
                win=margin>0
                spread=g.spread_line
                ats=None if pd.isna(spread) or abs(margin-spread)<1e-8 else bool(margin>spread)
                records.append({"season":int(year),"week":int(week),"game_id":g.game_id,
                    "matchup":g.away_team+" @ "+g.home_team,
                    "home_team":g.home_team,"home_ml":int(hml),
                    "away_ml":int(aml),"home_spread":float(spread) if pd.notna(spread) else None,
                    "home_edge_off":round(edge_off,4),"home_edge_def":round(edge_def,4),
                    "magnitude":round(min(edge_off,edge_def),4),
                    "magnitude_bucket":bucket(min(edge_off,edge_def)),
                    "win":bool(win),"ats_cover":ats,"elo_correct":bool(
                        elo.loc[g.game_id,"predicted_winner"] == g.home_team)==bool(win),
                    "reference_profit":round(100/abs(hml),5) if win else -1.0,
                    "margin":margin,"under_ten":bool(pd.notna(spread) and 0<spread<=10)})
    periods={"discovery_2019_2022":TRAIN,"holdout_2023_2025":TEST,
             "diagnostic_2026_ytd":CURRENT}
    result={"hypothesis":"NFL home favorite with both stronger prior-week standardized offense and defense. Weights EPA .40, rush .25, pass .15, turnovers .10, explosives .10. Min 3 prior complete games. ML -100 through -499.",
            "method":"NFL team stats and schedule, prior weeks only, current-season z scores among 16+ eligible NFL teams. No college-only P4/G6 or mid-magnitude exclusions. Historical reference closing ML/spread, not bookable prices.",
            "audits":audits,"periods":{},"years":{},
            "holdout_by_magnitude":{},"2026_by_week":{},"sensitivity":{},"records":records}
    for name,years in periods.items():
        result["periods"][name]=rate([r for r in records if r["season"] in years])
    for y in YEARS:
        result["years"][str(y)]=rate([r for r in records if r["season"]==y])
    for mag in ("0.00-0.24","0.25-0.49","0.50-0.74","0.75-0.99","1.00-1.49","1.50+"):
        result["holdout_by_magnitude"][mag]=rate([r for r in records if r["season"] in TEST and r["magnitude_bucket"]==mag])
    for week in sorted(set(r["week"] for r in records if r["season"]==2026)):
        result["2026_by_week"][str(week)]=rate([r for r in records if r["season"]==2026 and r["week"]==week])
    for p,years in periods.items():
        candidates=[r for r in records if r["season"] in years]
        result["sensitivity"][p]={"no_spread_cap":rate(candidates),
            "spread_at_most_10":rate([r for r in candidates if r["under_ten"]]),
            "exclude_magnitude_050_074":rate([r for r in candidates if r["magnitude_bucket"]!="0.50-0.74"])}
    result["by_season_magnitude"]={}
    for y in YEARS:
        result["by_season_magnitude"][str(y)]={
          mag:rate([r for r in records if r["season"]==y and r["magnitude_bucket"]==mag])
          for mag in ("0.00-0.24","0.25-0.49","0.50-0.74","0.75-0.99","1.00-1.49","1.50+")}
    result["exploratory_ranges"]={}
    for p,years in periods.items():
        group=[r for r in records if r["season"] in years]
        result["exploratory_ranges"][p]={
          "0.25_to_under_0.75":rate([r for r in group if .25<=r["magnitude"]<.75]),
          "at_least_0.25":rate([r for r in group if r["magnitude"]>=.25]),
          "below_0.25":rate([r for r in group if r["magnitude"]<.25])}
    return result

def main():
    games,stats=read_inputs()
    result=run(games,stats)
    finals=games[games.season.eq(2026) & games.home_score.notna() & games.away_score.notna()]
    print("2026 FINAL GAMES BY WEEK:",finals.groupby("week").size().to_dict(),flush=True)
    print("2026 QUALIFYING GAMES:",json.dumps([r for r in result["records"] if r["season"]==2026]),flush=True)
    Path("nfl_home_field_proposed_results.json").write_text(json.dumps(result,indent=2,allow_nan=False))
    print("NFL_HOME_FIELD_RESULTS_BEGIN",flush=True)
    print(json.dumps({k:v for k,v in result.items() if k!="records"},indent=2,allow_nan=False),flush=True)
    print("NFL_HOME_FIELD_RESULTS_END",flush=True)

if __name__=="__main__":
    main()

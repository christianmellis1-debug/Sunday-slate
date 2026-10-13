"""Sunday Slate pregame QB starter identity + replacement-quality research.

2019-24 NFLverse weekly depth charts: week-labeled retrospective source,
WITHOUT individual publication timestamps; not a confirmed as-of archive.
2025+: dated depth snapshots, strictly frozen BEFORE gameday 00:00 US/Eastern.
No future actual starter identity enters predictive features; outcome/coverage
audit and an explicitly hindsight-dependent oracle may use those identities.
All player EPA comes only from games in PRIOR weeks.
"""
from __future__ import annotations
import bisect
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from sunday_slate.data import load_schedules
from sunday_slate.model import predict_regular_season
from research.qb_replacement_quality_study import load_qb_boxes

TRAIN = (2019, 2020, 2021, 2022)
TEST = (2023, 2024, 2025)
ALIAS = {"LAR":"LA","JAC":"JAX","WSH":"WAS","SD":"LAC","OAK":"LV"}
MAX_DEPTH_AGE_DAYS = 14
SHRINK_DROPS = 150.0
QB_CAP = 0.45


def norm(x):
    val=str(x).strip().upper()
    return ALIAS.get(val,val)


def load_depths():
    import nflreadpy as nfl
    weekly={}
    for yr in (2019, 2020, 2021, 2022, 2023, 2024):
        try:
            frame=pd.DataFrame(nfl.load_depth_charts(seasons=yr).to_dicts())
        except Exception as exc:
            print("WEEKLY DEPTH MISSING",yr,repr(exc),flush=True)
            continue
        needed={"week","club_code","gsis_id","depth_team","depth_position","game_type"}
        if not needed.issubset(frame):
            raise ValueError("Historical depth missing: "+str(needed-set(frame)))
        frame=frame.loc[frame.game_type.eq("REG")
                        & frame.depth_position.eq("QB")
                        & pd.to_numeric(frame.depth_team,errors="coerce").eq(1)].copy()
        for entry in frame.to_dict("records"):
            gid=entry.get("gsis_id")
            wk=entry.get("week")
            if not gid or pd.isna(gid) or pd.isna(wk):
                continue
            key=(yr,int(wk),norm(entry["club_code"]))
            if key not in weekly:
                weekly[key]=str(gid)
    print("WEEKLY DEPTH COVERAGE",len(weekly),flush=True)
    dated={}
    for yr in (2025, 2026):
        try:
            frame=pd.DataFrame(nfl.load_depth_charts(seasons=yr).to_dicts())
        except Exception as exc:
            print("DATED DEPTH MISSING",yr,repr(exc),flush=True)
            continue
        needed={"dt","team","gsis_id","pos_rank","pos_abb"}
        if not needed.issubset(frame):
            raise ValueError("Dated depth missing: "+str(needed-set(frame)))
        q=frame.loc[frame.pos_abb.eq("QB")
                     & pd.to_numeric(frame.pos_rank,errors="coerce").eq(1)].copy()
        q["stamp"]=pd.to_datetime(q.dt,errors="coerce",utc=True)
        q=q.dropna(subset=["stamp","gsis_id","team"])
        q["team"]=q.team.map(norm)
        q=q.sort_values(["team","stamp","gsis_id"]).drop_duplicates(
            ["team","stamp"],keep="first")
        for team, part in q.groupby("team",sort=False):
            for record in part[["stamp","gsis_id"]].itertuples(index=False):
                dated.setdefault((yr,team),[]).append(
                    (record.stamp.value,str(record.gsis_id)))
        print("DATED DEPTH",yr,"QB1 records",len(q),
              "first",str(q.stamp.min()),"last",str(q.stamp.max()),flush=True)
    for key in dated:
        dated[key].sort()
    return weekly,dated


def choose_asof(weekly,dated,game,team):
    yr=int(game["season"])
    if yr <= 2024:
        return weekly.get((yr,int(game["week"]),norm(team))),None,"week-labeled"
    # PRE-DAY only, no same-day roster changes, and 14-day max staleness.
    date=pd.Timestamp(game["gameday"]).normalize()
    cutoff=date.tz_localize("America/New_York").tz_convert("UTC")
    series=dated.get((yr,norm(team)),[])
    i=bisect.bisect_left(series,(cutoff.value,""))-1
    if i<0:
        return None,None,"no-prior-snapshot"
    stamp,gid=series[i]
    age=(cutoff.value-stamp)/86400e9
    if not 0<age<=MAX_DEPTH_AGE_DAYS:
        return None,round(age,1),"stale"
    return gid,round(age,1),"dated-pre-day"


def features(schedule,boxes,weekly,dated):
    games=schedule.loc[schedule.game_type.eq("REG")
                        & schedule.season.ge(2014)].copy()
    games=games.sort_values(["season","week","game_id"],kind="stable")
    by_week={
        (int(y),int(w)):part.to_dict("records")
        for (y,w),part in boxes.groupby(["season","week"],sort=False)
    }
    career=defaultdict(lambda:[0.,0.])
    team_history=defaultdict(list)
    result=[]

    def quality(pid):
        if not pid or pd.isna(pid):
            return 0.
        ep,attempts=career[str(pid)]
        return float(np.clip(ep/(attempts+SHRINK_DROPS),-QB_CAP,QB_CAP))

    for (year,week),group in games.groupby(["season","week"],sort=True):
        for game in group.to_dict("records"):
            home=norm(game["home_team"]);away=norm(game["away_team"])
            sh=team_history[home];sa=team_history[away]
            oldH=sh[-1] if sh else None
            oldA=sa[-1] if sa else None
            depthH,ageH,statusH=choose_asof(weekly,dated,game,home)
            depthA,ageA,statusA=choose_asof(weekly,dated,game,away)
            realH=game.get("home_qb_id");realA=game.get("away_qb_id")
            realH=str(realH) if realH and pd.notna(realH) else None
            realA=str(realA) if realA and pd.notna(realA) else None
            priorH=quality(oldH);priorA=quality(oldA)
            qualityGap=priorH-priorA
            depthAvailable=int(bool(depthH and depthA))
            # A different QB only changes estimated team quality by the
            # difference in player EPA, never by a fixed injury penalty.
            depthDelta=(quality(depthH)-priorH if depthH else 0.
                        )-(quality(depthA)-priorA if depthA else 0.)
            trueDelta=(quality(realH)-priorH if realH else 0.
                       )-(quality(realA)-priorA if realA else 0.)
            result.append({
                "game_id":str(game["game_id"]),
                "depth_gap":depthDelta*10.,
                "prior_quality":qualityGap*10.,
                "depth_covered":depthAvailable,
                "oracle_gap":trueDelta*10.,
                "home_depth":depthH,
                "away_depth":depthA,
                "home_real":realH,
                "away_real":realA,
                "home_depth_age_days":ageH,
                "away_depth_age_days":ageA,
                "home_depth_status":statusH,
                "away_depth_status":statusA,
                "home_depth_correct":int(depthH==realH) if depthH and realH else None,
                "away_depth_correct":int(depthA==realA) if depthA and realA else None,
                "home_expected_change":int(bool(oldH and depthH and oldH!=depthH)),
                "away_expected_change":int(bool(oldA and depthA and oldA!=depthA)),
                "home_actual_change":int(bool(oldH and realH and oldH!=realH)),
                "away_actual_change":int(bool(oldA and realA and oldA!=realA)),
                "prior_home":oldH,"prior_away":oldA,
                "quality_home_depth":round(quality(depthH),5),
                "quality_away_depth":round(quality(depthA),5),
                "quality_home_old":round(priorH,5),
                "quality_away_old":round(priorA,5),
                "date":str(game.get("gameday"))
            })
        # Freeze entire week before accumulating current-week player data.
        for player in by_week.get((int(year),int(week)),[]):
            state=career[str(player["player_id"])]
            state[0]+=float(player["passing_epa"])
            state[1]+=float(player["drops"])
        for game in group.to_dict("records"):
            if pd.isna(game["home_score"]) or pd.isna(game["away_score"]):
                continue
            for team,pid in ((norm(game["home_team"]),game.get("home_qb_id")),
                             (norm(game["away_team"]),game.get("away_qb_id"))):
                if pid and pd.notna(pid):
                    team_history[team].append(str(pid))
    return pd.DataFrame.from_records(result)


def assess(schedule,boxes,weekly,dated):
    elo=predict_regular_season(schedule)
    feats=features(schedule,boxes,weekly,dated)
    data=elo.merge(feats,on="game_id",validate="one_to_one")
    data=data[data.pick_result.isin(["Correct","Incorrect"])
              & data.season.between(2019,2026)].copy()
    data["actual"]=(data.pick_result.eq("Correct")
                    ==data.predicted_winner.eq(data.home_team)).astype(int)
    p=data.home_probability.clip(1e-8,1-1e-8)
    data["elo_logit"]=np.log(p/(1-p))
    candidates={
        "elo_recalibrated":["elo_logit"],
        "pregame_previous_qb_quality":["elo_logit","prior_quality"],
        "pregame_depth_replacement":["elo_logit","prior_quality","depth_gap","depth_covered"],
        "pregame_depth_delta_only":["elo_logit","depth_gap","depth_covered"],
        "oracle_actual_starter":["elo_logit","prior_quality","oracle_gap"],
    }
    train=data[data.season.isin(TRAIN)]
    if len(train)!=1050:raise ValueError("Unexpected train count: "+str(len(train)))
    trained={}
    for name,cols in candidates.items():
        pipe=make_pipeline(StandardScaler(),LogisticRegression(C=1.0,max_iter=2000,solver="lbfgs"))
        pipe.fit(train[cols].fillna(0),train.actual)
        data[name]=pipe.predict_proba(data[cols].fillna(0))[:,1]
        lr=pipe.named_steps["logisticregression"]
        trained[name]={"features":cols,"coefficients":lr.coef_[0].tolist(),
                       "intercept":float(lr.intercept_[0])}

    def metric(part, col):
        if not len(part):return {"games":0}
        y=part.actual.to_numpy(dtype=float)
        q=part[col].to_numpy(dtype=float)
        hits=int(((q>=0.5)==(y==1)).sum())
        return {"games":len(part),"wins":hits,"losses":len(part)-hits,
                "accuracy_pct":round(100*hits/len(part),2),
                "brier":round(float(np.mean((q-y)**2)),5)}
    periods={
        "2019-2022_fit":TRAIN,
        "2023-2024_weekly_depth_retrospective":(2023,2024),
        "2025_time-stamped_depth":(2025,),
        "2026_to_date_time-stamped_depth":(2026,),
        "2023-2025_retrospective":TEST,
    }
    periods.update({str(y):(y,) for y in range(2019,2027)})
    result={}
    for key,years in periods.items():
        part=data[data.season.isin(years)]
        counts={"games":len(part),
                "both_depth_available":int(part.depth_covered.sum()),
                "depth_predicted_changed_any":int((part.home_expected_change|part.away_expected_change).sum()),
                "actual_changed_any":int((part.home_actual_change|part.away_actual_change).sum())}
        for side in ("home","away"):
            v=part[f"{side}_depth_correct"].dropna()
            counts[f"{side}_qb1_hit"]={"n":len(v),"correct":int(v.sum()),
                "accuracy_pct":round(100*v.mean(),2) if len(v) else None}
        for label,group in {
            "all":part,
            "depth_both_present":part[part.depth_covered.eq(1)],
            "depth_qb_change_predicted":part[(part.home_expected_change|part.away_expected_change).eq(1)],
            "actual_starter_change_oracle_diagnostic":part[(part.home_actual_change|part.away_actual_change).eq(1)]
        }.items():
            counts[label]={"elo_unmodified":metric(group,"home_probability")}
            for name in candidates:counts[label][name]=metric(group,name)
        result[key]=counts
    examples={}
    for gid in ("2025_05_HOU_BAL","2025_18_WAS_PHI","2025_16_KC_TEN",
                "2025_04_WAS_ATL","2025_01_MIN_CHI"):
        row=data.loc[data.game_id.eq(gid)]
        if len(row):
            r=row.iloc[0]
            examples[gid]={
                "gameday":r.date,"depth_home_qb":r.home_depth,
                "actual_home_qb":r.home_real,"depth_away_qb":r.away_depth,
                "actual_away_qb":r.away_real,
                "depth_gap":round(float(r.depth_gap),4),
                "elo_pick":r.predicted_winner,
                "elo_probability":round(float(r.pick_probability),4),
                "depth_probability":round(float(r.pregame_depth_replacement),4),
                "depth_pick":r.home_team if r.pregame_depth_replacement>=0.5 else r.away_team,
                "depth_status_home":r.home_depth_status,
                "depth_status_away":r.away_depth_status,
                "correct":r.pick_result
            }
    return {
        "method":{"training_years":list(TRAIN),
                  "2019_2024_warning":"Weekly depth chart has week but not historical publication timestamp",
                  "2025_2026_asof":"latest depth snapshot strictly before game-day 00:00 America/New_York, max 14 days old",
                  "qb1_not_confirmed_starter":True,
                  "qb_stats_prior_week_only":True,
                  "oracle_not_pregame_valid":True,
                  "no_live_model_change":True},
        "player_weeks":len(boxes),"depth_weekly_keys":len(weekly),
        "dated_snapshot_keys":sum(len(x) for x in dated.values()),
        "fitted":trained,"results":result,"examples":examples
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default="qb_pregame_availability_results.json")
    args=parser.parse_args()
    schedule=load_schedules()
    for col in ("season","week","home_score","away_score"):
        schedule[col]=pd.to_numeric(schedule[col],errors="coerce")
    print("Loading QB statistics and depth charts...",flush=True)
    boxes=load_qb_boxes()
    weekly,dated=load_depths()
    report=assess(schedule,boxes,weekly,dated)
    text=json.dumps(report,indent=2,allow_nan=False)
    print("QB_PREGAME_AVAILABILITY_BEGIN\n"+text+"\nQB_PREGAME_AVAILABILITY_END",flush=True)
    Path(args.output).write_text(text+"\n")


if __name__=="__main__":main()

"""As-of current 2026 week-6 QB research snapshot, no publication or Elo change."""
import json
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
from sunday_slate.data import load_schedules,load_qb_depth_charts,load_player_stats,load_injury_reports,FeedError
from sunday_slate.metrics import with_kickoffs
from sunday_slate.qb_availability import context
from sunday_slate.model import predict_regular_season

def main():
    now=datetime.now(timezone.utc)
    all_games=with_kickoffs(load_schedules())
    slate=all_games.loc[(all_games.season==2026) &
                        (all_games.game_type=="REG")&(all_games.week==6)].copy()
    if slate.empty:raise ValueError("2026 Week 6 not in live schedule")
    depth=load_qb_depth_charts(2026)
    players=load_player_stats(2026)
    injury_note=None
    try:
        injuries=load_injury_reports(2026)
        injury_note=f"Injury records loaded: {len(injuries)}"
    except FeedError as exc:
        injuries=pd.DataFrame()
        injury_note=f"Timestamp-valid injury records unavailable: {exc}"
    # Predict only for the Week 6 game display; official Elo untouched.
    elo=predict_regular_season(all_games)
    elo_map={str(r.game_id):r for r in elo.itertuples(index=False)}
    games=[]
    for g in slate.sort_values(["kickoff_ct","game_id"]).to_dict("records"):
        info=context(g,all_games,depth,players,injuries,{},now)
        teams={}
        for team,t in info["teams"].items():
            projected=t.get("expected") or {}
            teams[team]={
              "projected_starter":projected.get("name"),
              "projected_gsis_id":projected.get("gsis_id"),
              "previous_starter_id":(t.get("previous") or {}).get("gsis_id"),
              "previous_week":(t.get("previous") or {}).get("week"),
              "listed_backup":(t.get("depth_backup") or {}).get("name"),
              "depth_snapshot_time":t.get("depth_asof"),
              "identification":t.get("classification"),
              "injury_status":t.get("report"),
              "starter_change_indicated":t.get("change_indicated"),
              "replacement_epa_difference":t.get("replacement_delta_epa"),
              "qb_quality_old":t.get("old_quality"),
              "qb_quality_candidate":t.get("expected_quality")
            }
        match=elo_map.get(str(g["game_id"]))
        games.append({
            "game_id":str(g["game_id"]),
            "date":str(g["gameday"]),
            "kickoff_CT":str(g["kickoff_ct"]),
            "home":str(g["home_team"]),
            "away":str(g["away_team"]),
            "teams":teams,
            "official_elo_pick":(match.predicted_winner if match is not None else None),
            "official_elo_pick_probability":(round(float(match.pick_probability),4) if match is not None else None),
        })
    output={
      "asof_utc":now.isoformat(),"season":2026,"week":6,
      "injury_note":injury_note,"games":games,
      "total_games":len(games),
      "projected_qbs_with_changes":[{"game_id":g["game_id"],"team":team,**{k:d.get(k) for k in ["projected_starter","previous_starter_id","replacement_epa_difference","injury_status","identification"]}}
        for g in games for team,d in g["teams"].items() if d["starter_change_indicated"]],
      "missing_qb_projection_count":sum(not d["projected_starter"] for g in games for d in g["teams"].values()),
      "qb_dated_injuries":sum(bool(d["injury_status"]) for g in games for d in g["teams"].values()),
      "owner_confirmations":0,
      "caution":"Projected QB1 and injury reports are not a confirmed starter; no official Elo override."
    }
    text=json.dumps(output,indent=2,default=str)
    print("QB_LIVE_RESULTS_BEGIN\n"+text+"\nQB_LIVE_RESULTS_END",flush=True)
    Path("qb_live_2026_week6.json").write_text(text+"\n")

if __name__=="__main__":main()

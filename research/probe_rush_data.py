"""Inspect nflverse play-by-play rushing fields without modifying app models."""
import nflreadpy

print("DATA_PROBE_START")
team=nflreadpy.load_team_stats(seasons=[2024],summary_level="week")
print("TEAM_STATS_COLUMNS",team.columns)
print("TEAM_RUSH_SAMPLE",team.select([c for c in ["season","week","team","game_id","rushing_epa","carries","rushing_success_rate","rushing_success"] if c in team.columns]).head(3).to_dicts())
pbp=nflreadpy.load_pbp(seasons=[2024])
print("PBP_SHAPE",pbp.shape)
print("PBP_RELEVANT_COLUMNS",[c for c in pbp.columns if any(part in c for part in ("rush","success","epa","score_differential","wp","qtr","play_type","posteam","defteam","game_id","week","down","qb_scramble","qb_kneel","season_type","yardline","spread_line"))])
cols=[c for c in ("game_id","season","week","season_type","posteam","defteam","play_type","rush_attempt","qb_scramble","qb_kneel","epa","success","score_differential","qtr","wp") if c in pbp.columns]
print("PBP_RUSH_SAMPLE",pbp.select(cols).filter((__import__("polars").col("play_type")=="run")).head(5).to_dicts() if "play_type" in pbp.columns else [])
print("DATA_PROBE_FINISH")

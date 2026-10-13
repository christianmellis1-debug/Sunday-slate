"""Pregame QB Availability Confirmation (research-only; never changes Elo picks).

Depth charts are PROJECTIONS, not verified starts. An optional Streamlit-secret
owner-researched NFL announcement upgrades identity attribution only when it
contains an NFL URL and an independently entered pre-kickoff publication time.
That URL is not programmatically verified. Historic/undated injuries fail closed.
"""
from __future__ import annotations

import json
import math
from urllib.parse import urlsplit
import pandas as pd

MAX_DEPTH_DAYS = 14
SHRINK_DROPBACKS = 150.0
CLIP_EPA = 0.45


def norm_team(value: object) -> str:
    code = str(value or "").strip().upper()
    return {"LAR": "LA", "JAC": "JAX", "WSH": "WAS",
            "SD": "LAC", "OAK": "LV"}.get(code, code)


def utc(value: object):
    try:
        ts = pd.to_datetime(value, utc=True, errors="coerce")
        return None if pd.isna(ts) else ts
    except (TypeError, ValueError, OverflowError):
        return None


def read_owner_confirmations(value: object) -> dict:
    """Private owner-supplied information; never fetch arbitrary URLs."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return {}
    return value if isinstance(value, dict) else {}


def is_nfl_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        u = urlsplit(value)
        return (u.scheme == "https" and not u.username and not u.password
                and (u.hostname == "nfl.com" or (u.hostname or "").endswith(".nfl.com"))
                and u.port in (None, 443) and len(value) < 2048)
    except ValueError:
        return False


def approved_announcement(confirmations: dict, game_id: str, team: str,
                          now: object, kickoff: object) -> dict | None:
    """Validate provenance; owner's citation is not automatically fact-checked."""
    item = (confirmations.get(game_id) or {}) if isinstance(confirmations, dict) else {}
    item = item.get(norm_team(team)) if isinstance(item, dict) else None
    if not isinstance(item, dict):
        return None
    ts,now_ts,ko = utc(item.get("reported_at")),utc(now),utc(kickoff)
    gsis, name, url = item.get("gsis_id"),item.get("player_name"),item.get("source_url")
    if (None in (ts,now_ts,ko) or not isinstance(gsis,str)
        or not gsis.startswith("00-") or not isinstance(name,str)
        or not 2 <= len(name.strip()) <= 100 or not is_nfl_url(url)
        or ts > now_ts or ts >= ko or ts < ko-pd.Timedelta(days=14)):
        return None
    return {"gsis_id": gsis, "name":name.strip(),
            "source_url":url, "reported_at":ts.isoformat(),
            "provenance":"Owner-supplied NFL announcement; URL not automatically verified"}


def latest_depth(depth: pd.DataFrame | None, team: str, at: object,
                 max_age_days: int = MAX_DEPTH_DAYS) -> dict:
    """Last *complete* time-stamped QB depth chart strictly before cutoff."""
    fallback={"starter": None, "backup":None, "alternates":[],
              "source":"unavailable","asof":None}
    at_ts=utc(at)
    needed={"dt","team","pos_abb","pos_rank","gsis_id"}
    if (at_ts is None or depth is None or depth.empty
            or not needed.issubset(depth.columns)):
        return fallback
    rows=depth[depth["team"].astype(str).map(norm_team).eq(norm_team(team))
               & depth["pos_abb"].astype(str).eq("QB")].copy()
    if rows.empty:
        return fallback
    rows["stamp"]=pd.to_datetime(rows["dt"],errors="coerce",utc=True)
    rows["rank"]=pd.to_numeric(rows["pos_rank"],errors="coerce")
    rows=rows[rows.stamp.notna() & rows.stamp.lt(at_ts)
              & rows.stamp.ge(at_ts-pd.Timedelta(days=max_age_days))
              & rows["rank"].between(1, 5) & rows.gsis_id.notna()]
    if rows.empty:
        return fallback
    last=rows.stamp.max()
    slate=rows[rows.stamp.eq(last)].sort_values(["rank","gsis_id"])
    players=[]
    for rec in slate.to_dict("records"):
        gid=str(rec["gsis_id"])
        if not gid.startswith("00-") or any(x["gsis_id"]==gid for x in players):
            continue
        players.append({"gsis_id":gid,"name":str(rec.get("player_name") or gid),
                        "rank":int(rec["rank"])})
    first=next((x for x in players if x["rank"]==1),None)
    if first is None:
        return fallback
    other=[x for x in players if x["gsis_id"]!=first["gsis_id"]]
    return {"starter":first,"backup":other[0] if other else None,
            "alternates":other,"source":"Timestamped NFLverse QB depth-chart projection",
            "asof":last.isoformat()}


def prior_starter(schedule: pd.DataFrame, team: str, season: int,
                  week: int) -> dict | None:
    """Only most recent earlier-week completed regular-season game."""
    need={"season","week","game_type","home_team","away_team",
          "home_score","away_score","home_qb_id","away_qb_id"}
    if schedule is None or schedule.empty or not need.issubset(schedule):
        return None
    games=schedule[
        (pd.to_numeric(schedule.season,errors="coerce")==season)
        & pd.to_numeric(schedule.week,errors="coerce").lt(week)
        & schedule.game_type.eq("REG")
        & (schedule.home_team.astype(str).map(norm_team).eq(norm_team(team))
           | schedule.away_team.astype(str).map(norm_team).eq(norm_team(team)))
        & pd.to_numeric(schedule.home_score,errors="coerce").notna()
        & pd.to_numeric(schedule.away_score,errors="coerce").notna()
    ].sort_values(["week","game_id"] if "game_id" in schedule else ["week"])
    for g in reversed(games.to_dict("records")):
        is_home=norm_team(g["home_team"])==norm_team(team)
        value=g.get("home_qb_id" if is_home else "away_qb_id")
        if isinstance(value,str) and value.startswith("00-"):
            return {"gsis_id":value,"name":None,"week":int(g["week"])}
    return None


def prior_qb_quality(player_stats: pd.DataFrame | None, season: int,
                     week: int, qb_id: str | None) -> dict | None:
    """Season-local earlier weeks only, not a player's future performance."""
    fields={"season","week","position","player_id","passing_epa","attempts","sacks_suffered"}
    if not qb_id or player_stats is None or player_stats.empty or not fields.issubset(player_stats):
        return None
    rows=player_stats[
        pd.to_numeric(player_stats.season,errors="coerce").eq(season)
        & pd.to_numeric(player_stats.week,errors="coerce").lt(week)
        & player_stats.position.eq("QB")
        & player_stats.player_id.astype(str).eq(qb_id)
    ].copy()
    if "season_type" in rows:
        rows=rows[rows.season_type.eq("REG")]
    if rows.empty:
        return None
    epa=pd.to_numeric(rows.passing_epa,errors="coerce")
    attempts=pd.to_numeric(rows.attempts,errors="coerce")
    sacks=pd.to_numeric(rows.sacks_suffered,errors="coerce")
    valid=epa.notna()&attempts.notna()&sacks.notna()&attempts.ge(0)&sacks.ge(0)
    if not valid.any():
        return None
    drops=float((attempts[valid]+sacks[valid]).sum())
    if drops<=0:
        return None
    ep=float(epa[valid].sum())
    rate=max(-CLIP_EPA,min(CLIP_EPA,ep/(drops+SHRINK_DROPBACKS)))
    return {"epa_per_dropback":round(rate,4),"sample_dropbacks":int(drops),
            "window":"Current season, completed prior weeks; +150 neutral pseudo-dropbacks"}


def dated_qb_injury(injuries: pd.DataFrame | None, season: int, week: int,
                    team: str, qb_id: str | None, now: object, kickoff: object) -> dict | None:
    """Only latest dated row with actual game status; no date -> no finding."""
    required={"season","week","team","gsis_id","position","report_status","date_modified"}
    if (not qb_id or injuries is None or injuries.empty or not required.issubset(injuries)):
        return None
    ko,now_ts=utc(kickoff),utc(now)
    if ko is None or now_ts is None:
        return None
    cutoff=min(ko,now_ts)
    rows=injuries[
        pd.to_numeric(injuries.season,errors="coerce").eq(season)
        & pd.to_numeric(injuries.week,errors="coerce").eq(week)
        & injuries.team.astype(str).map(norm_team).eq(norm_team(team))
        & injuries.gsis_id.astype(str).eq(qb_id)
        & injuries.position.astype(str).eq("QB")
    ].copy()
    if rows.empty:
        return None
    rows["modified"]=pd.to_datetime(rows.date_modified,utc=True,errors="coerce")
    rows=rows[rows.modified.notna()&rows.modified.le(cutoff)
              & rows.modified.ge(ko-pd.Timedelta(days=8))]
    if rows.empty:
        return None
    r=rows.sort_values("modified").iloc[-1]
    status=str(r.report_status).strip().upper()
    if status not in {"OUT","DOUBTFUL","QUESTIONABLE"}:
        return None
    return {"status":status.title(),"updated_at":r.modified.isoformat(),
            "source":"NFLverse source-dated game-week injury status (not confirmed inactives)"}


def context(game: dict, schedule: pd.DataFrame, depth: pd.DataFrame | None,
            player_stats: pd.DataFrame | None, injuries: pd.DataFrame | None,
            confirmations: dict | None, now: object) -> dict:
    """One-game rendering data. No model picks or probability changes."""
    now_ts=utc(now)
    kickoff=utc(game.get("kickoff_ct"))
    if kickoff is None or now_ts is None:
        return {"available":False,"reason":"Missing kickoff or current UTC time"}
    # Two hours is a pregame evaluation cutoff. Unconfirmed QB charts may
    # update closer than this; official announcements have their own timestamp.
    cutoff=min(now_ts,kickoff-pd.Timedelta(hours=2))
    result={"available":True,"kickoff":kickoff.isoformat(),
            "snapshot_cutoff":cutoff.isoformat(),
            "teams":{},"official_elo_unchanged":True}
    for team in (norm_team(game["away_team"]),norm_team(game["home_team"])):
        depth_info=latest_depth(depth,team,cutoff)
        prev=prior_starter(schedule,team,int(game["season"]),int(game["week"]))
        ann=approved_announcement(confirmations or {},str(game["game_id"]),
                                  team,now_ts,kickoff)
        selected=({"gsis_id":ann["gsis_id"],"name":ann["name"],"rank":None}
                  if ann else depth_info["starter"])
        previous_id=prev["gsis_id"] if prev else None
        expected_id=selected["gsis_id"] if selected else None
        old_rate=prior_qb_quality(player_stats,int(game["season"]),int(game["week"]),previous_id)
        new_rate=prior_qb_quality(player_stats,int(game["season"]),int(game["week"]),expected_id)
        delta=(round(new_rate["epa_per_dropback"]-old_rate["epa_per_dropback"],4)
               if previous_id and expected_id and previous_id!=expected_id
               and old_rate and new_rate else None)
        injury=dated_qb_injury(injuries,int(game["season"]),int(game["week"]),
                              team,expected_id,now_ts,kickoff)
        if ann:
            classification="Owner-reviewed NFL source (not independently verified by app)"
        elif selected and injury and injury["status"]=="Out":
            classification="Projected QB listed OUT — starter unconfirmed"
        elif selected:
            classification="Depth-chart projection — unconfirmed"
        else:
            classification="Starter unavailable — no reliable projected QB"
        result["teams"][team]={
            "team":team,"projected":depth_info["starter"],
            "depth_backup":depth_info["backup"],
            "depth_asof":depth_info["asof"],
            "expected":selected,"confirmation":ann,
            "previous":prev,"report":injury,"classification":classification,
            "old_quality":old_rate,"expected_quality":new_rate,
            "replacement_delta_epa":delta,
            "change_indicated":bool(previous_id and expected_id and previous_id!=expected_id),
            "depth_source":depth_info["source"]}
    return result

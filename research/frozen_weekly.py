"""Frozen research-only Elo vs EPA/form forecasts, with pre-kickoff weekly archives.

Run one time before that NFL week's first kickoff. Does NOT edit app predictions.
The saved JSON is append-only; existing files are never overwritten.
No sportsbook odds; all statistics must predate the target NFL week.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from backtests.experimental_research import preweek_features
from research.model_epa_qbr_study import load_stats, make_features
from sunday_slate.data import load_schedules
from sunday_slate.model import predict_regular_season

CONFIG = Path(__file__).with_name("frozen_form_epa_v1.json")
SNAPSHOTS = Path(__file__).with_name("snapshots")
COLUMNS = ("eloDiff", "recent_margin_feature", "p_adj", "r_adj")


def load_frozen(path: Path = CONFIG) -> dict:
    cfg = json.loads(path.read_text())
    if tuple(cfg["columns"]) != COLUMNS or cfg["training_years"] != [2019, 2020, 2021, 2022]:
        raise ValueError("Unrecognized frozen research model schema")
    if any(len(cfg[k]) != 4 for k in ("coef", "mean", "scale")):
        raise ValueError("Bad frozen coefficient lengths")
    if any(not math.isfinite(float(v)) for k in ("coef", "mean", "scale")
           for v in cfg[k]) or not all(float(s) > 0 for s in cfg["scale"]):
        raise ValueError("Invalid coefficients or scales")
    return cfg


def challenger_probability(row: dict, cfg: dict) -> float:
    score = float(cfg["intercept"])
    for i, key in enumerate(cfg["columns"]):
        val = row.get(key)
        try:
            v = float(val)
            if not math.isfinite(v):
                v = 0.0
        except (ValueError, TypeError):
            v = 0.0
        score += float(cfg["coef"][i]) * (v - float(cfg["mean"][i])) / float(cfg["scale"][i])
    return 1. / (1. + math.exp(-max(-35., min(35., score))))


def predictions(schedule: pd.DataFrame, weekly_team: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Full history in, unscored and scored games out; no model fitting."""
    elo = predict_regular_season(schedule)
    empty_qbr = pd.DataFrame(columns=["season", "week_num", "team_abb", "player_id",
                                      "qbr_total", "qb_plays"])
    epa = make_features(schedule, weekly_team, empty_qbr)
    form = preweek_features(schedule)
    if epa.empty or elo.empty or form.empty:
        raise ValueError("No historical features")
    joined = elo.merge(
        epa[["game_id", "p_adj", "r_adj", "min_games"]],
        on="game_id", validate="one_to_one",
    ).merge(
        form[["game_id", "recent_margin_feature", "ppg_projected_margin", "min_prior_games"]],
        on="game_id", validate="one_to_one",
    )
    joined["eloDiff"] = (joined.home_elo - joined.away_elo
                         + joined.home_field_elo + joined.rest_elo) / 100.
    joined["challenger_home_probability"] = joined.apply(
        lambda r: challenger_probability(r.to_dict(), cfg), axis=1,
    )
    joined["challenger_winner"] = joined.apply(
        lambda r: r.home_team if r.challenger_home_probability >= 0.5
        else r.away_team, axis=1,
    )
    return joined


def select_upcoming_week(preds: pd.DataFrame, schedule: pd.DataFrame,
                         when: datetime) -> tuple[int, int, pd.DataFrame]:
    """Earliest fully unplayed REG week with a kickoff no more than 14 days out."""
    raw = schedule[["game_id", "gameday", "home_score", "away_score"]].copy()
    raw["gameday"] = pd.to_datetime(raw["gameday"], errors="coerce", utc=True)
    joined = preds.merge(raw, on="game_id", validate="one_to_one")
    today = pd.Timestamp(when).tz_convert("UTC")
    eligible = []
    for (season, week), sub in joined.groupby(["season", "week"], sort=True):
        if int(season) < today.year or int(season) > today.year:
            continue
        if sub["home_score"].notna().any() or sub["away_score"].notna().any():
            continue
        first = sub["gameday"].min()
        if pd.isna(first):
            continue
        if (first - today).total_seconds() < -86400:
            continue
        if (first - today).total_seconds() > 14 * 86400:
            continue
        eligible.append((first, int(season), int(week), sub))
    if not eligible:
        raise RuntimeError("No complete, unplayed NFL week within the next 14 days; no snapshot written")
    _, season, week, records = sorted(eligible, key=lambda x: x[0])[0]
    return season, week, records


def archive_next_week(schedule: pd.DataFrame, stats: pd.DataFrame,
                      when: datetime, root: Path = SNAPSHOTS) -> dict:
    cfg = load_frozen()
    pred = predictions(schedule, stats, cfg)
    season, week, games = select_upcoming_week(pred, schedule, when)
    path = root / f"{season}_week_{week:02d}.json"
    if path.exists():
        raise FileExistsError(f"Frozen snapshot already exists: {path}")
    # Ensure first kickoff is in the future; schedule's gameday is date-only,
    # so refuse same-day snapshots rather than guess kickoff time.
    first = games["gameday"].min()
    if first.normalize() <= pd.Timestamp(when).tz_convert("UTC").normalize():
        raise RuntimeError("First game is already today; cannot verify pre-kickoff freshness")
    required_lookback = 3
    results = []
    for game in games.sort_values("game_id").to_dict("records"):
        if int(game["min_games"]) < 0 or int(game["min_prior_games"]) < 0:
            raise ValueError("Negative historical game count")
        row = {
            "game_id": str(game["game_id"]),
            "home_team": str(game["home_team"]),
            "away_team": str(game["away_team"]),
            "elo_home_probability": round(float(game["home_probability"]), 8),
            "elo_winner": str(game["predicted_winner"]),
            "challenger_home_probability": round(float(game["challenger_home_probability"]), 8),
            "challenger_winner": str(game["challenger_winner"]),
            "elo_confidence": round(float(game["pick_probability"]), 8),
            "ppg_margin": (round(float(game["ppg_projected_margin"]), 4)
                           if pd.notna(game["ppg_projected_margin"]) else None),
            "prior_games_min": int(game["min_prior_games"]),
            "epa_prior_games_min": int(game["min_games"]),
            "eligibility_note": ("EPA limited history" if int(game["min_games"]) < required_lookback
                                 else "EPA history available"),
        }
        results.append(row)
    digest = hashlib.sha256(json.dumps(results, sort_keys=True).encode()).hexdigest()
    payload = {
        "model": cfg["version"], "model_parameters_sha256": hashlib.sha256(
            CONFIG.read_bytes()).hexdigest(),
        "season": season, "week": week,
        "created_at_utc": when.isoformat(),
        "source_commit": os.environ.get("GITHUB_SHA", "manual"),
        "source": "NFLverse preweek stats; no odds",
        "history_is_pregame": True,
        "snapshot_sha256": digest,
        "games": results,
    }
    root.mkdir(parents=True, exist_ok=True)
    with path.open("x") as target:
        json.dump(payload, target, indent=2, allow_nan=False)
        target.write("\n")
    return {"file": str(path), "season": season, "week": week,
            "games": len(results), "elo_agree": sum(g["elo_winner"] ==
            g["challenger_winner"] for g in results), "sha256": digest}


def grade_archive(schedule: pd.DataFrame, root: Path = SNAPSHOTS) -> dict:
    """Score only the actual archived probability; never regenerate old predictions."""
    source = schedule.set_index("game_id")
    report = []
    for file in sorted(root.glob("20??_week_??.json")):
        payload = json.loads(file.read_text())
        wins_elo = wins_challenger = done = pending = 0
        for record in payload["games"]:
            gid = record["game_id"]
            if gid not in source.index:
                pending += 1
                continue
            line = source.loc[gid]
            hs, aws = pd.to_numeric(line["home_score"], errors="coerce"), pd.to_numeric(line["away_score"], errors="coerce")
            if pd.isna(hs) or pd.isna(aws) or hs == aws:
                pending += 1
                continue
            actual = record["home_team"] if hs > aws else record["away_team"]
            done += 1
            wins_elo += int(record["elo_winner"] == actual)
            wins_challenger += int(record["challenger_winner"] == actual)
        report.append({"season": payload["season"], "week": payload["week"],
                       "total": len(payload["games"]),
                       "graded": done, "pending_or_tie": pending,
                       "elo": {"wins": wins_elo, "losses": done - wins_elo},
                       "challenger": {"wins": wins_challenger, "losses": done - wins_challenger},
                       "snapshot_sha256": payload["snapshot_sha256"]})
    return {"snapshots": report, "total_graded": sum(x["graded"] for x in report),
            "note": "Grades only pregame archived predictions; snapshots are never rewritten."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["snapshot", "grade"], default="snapshot")
    parser.add_argument("--date-utc", help="ISO timestamp; defaults to actual UTC now")
    parser.add_argument("--output", default="weekly_snapshot_report.json")
    args = parser.parse_args()
    now = datetime.fromisoformat(args.date_utc) if args.date_utc else datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("UTC timestamp must include timezone")
    schedule = load_schedules()
    if args.mode == "grade":
        result = grade_archive(schedule)
    else:
        stats = load_stats()
        try:
            result = archive_next_week(schedule, stats, now)
        except FileExistsError as exc:
            # Scheduled reruns must never mutate an existing frozen snapshot.
            result = {"status": "existing snapshot retained", "reason": str(exc)}
        except RuntimeError as exc:
            if ("No complete, unplayed NFL week" not in str(exc)
                    and "First game is already today" not in str(exc)):
                raise
            # Continue with grading on non-slate/holiday weeks.
            result = {"status": "no safe upcoming pregame snapshot", "reason": str(exc)}
    Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

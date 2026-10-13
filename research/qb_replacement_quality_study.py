"""Research: quarterback replacement quality vs Sunday Slate's frozen Elo.

Two separate questions:
1. PREGAME: Can last known starter quality and a completed previous-week
   QB change improve the model? All features use PRIOR weeks only.
2. ORACLE: If the upcoming game's actual starting QB were known, would
   replacing last week's presumed QB with that player's PRE-GAME EPA help?
   Actual starter identity is hindsight here, so not deployable.

No injury-status archive or timestamped projected-starter feed is used.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from sunday_slate.data import load_schedules
from sunday_slate.model import predict_regular_season

TRAIN = (2019, 2020, 2021, 2022)
EVAL = (2023, 2024, 2025)
YEARS = TRAIN + EVAL + (2026,)
QB_PRIOR_PLAYS = 150.0
QB_EPA_CLIP = 0.45


def load_qb_boxes(path=None):
    if path:
        raw = pd.read_csv(path, low_memory=False)
    else:
        import nflreadpy
        raw = pd.DataFrame(
            nflreadpy.load_player_stats(
                seasons=list(range(2014, 2027)), summary_level="week"
            ).to_dicts()
        )
    fields = {"player_id", "season", "week", "season_type",
              "position", "passing_epa", "attempts", "sacks_suffered"}
    if not fields.issubset(raw):
        raise ValueError("Missing player stat columns: " + repr(fields-set(raw)))
    x = raw.loc[raw.season_type.eq("REG") & raw.position.eq("QB"),
                list(fields)].copy()
    for col in ("season", "week", "passing_epa", "attempts", "sacks_suffered"):
        x[col] = pd.to_numeric(x[col], errors="coerce")
    x = x.dropna(subset=["player_id", "season", "week", "passing_epa",
                          "attempts", "sacks_suffered"])
    x["drops"] = x.attempts + x.sacks_suffered
    x = x[x.drops.gt(0) & x.week.ge(1)].copy()
    if x.duplicated(["season", "week", "player_id"]).any():
        raise ValueError("Duplicate weekly quarterback/player rows")
    return x


def prior_features(schedule, boxes):
    games = schedule[schedule.game_type.eq("REG")].copy()
    games = games[games.season.ge(2014)].sort_values(
        ["season", "week", "game_id"], kind="stable")
    stats_by_week = {
        key: group.to_dict("records")
        for key, group in boxes.groupby(["season", "week"], sort=False)
    }
    career = defaultdict(lambda: [0., 0.])
    team_starters = defaultdict(list)
    records = []

    def rating(pid):
        if not pid or pd.isna(pid):
            return 0.
        epa, drops = career[str(pid)]
        # 150 dropbacks of league-average (zero EPA) shrink the estimate
        return float(np.clip(epa / (drops + QB_PRIOR_PLAYS),
                             -QB_EPA_CLIP, QB_EPA_CLIP))

    for (season, week), slate in games.groupby(["season", "week"], sort=True):
        # Compute ALL upcoming games' features before any same-week updates
        for game in slate.to_dict("records"):
            h, a = str(game["home_team"]), str(game["away_team"])
            sh, sa = team_starters[h], team_starters[a]
            expected_h = sh[-1] if sh else None
            expected_a = sa[-1] if sa else None
            earlier_h = sh[-2] if len(sh) > 1 else None
            earlier_a = sa[-2] if len(sa) > 1 else None
            observed_h = game.get("home_qb_id")
            observed_a = game.get("away_qb_id")

            def previous_change(previous, earlier):
                if not previous or not earlier or previous == earlier:
                    return 0.
                return rating(previous) - rating(earlier)

            # Entirely pregame-observable from past results.
            pre_quality = rating(expected_h) - rating(expected_a)
            pre_switch = (previous_change(expected_h, earlier_h)
                          - previous_change(expected_a, earlier_a))
            # NOT a deployable feature: actual starter identity only
            # known retrospectively; QB EPA values still prior-week only.
            home_new = (bool(expected_h and observed_h)
                        and str(expected_h) != str(observed_h))
            away_new = (bool(expected_a and observed_a)
                        and str(expected_a) != str(observed_a))
            oracle_delta = (
                (rating(observed_h) - rating(expected_h) if home_new else 0.)
                - (rating(observed_a) - rating(expected_a) if away_new else 0.)
            )
            records.append({
                "game_id": game["game_id"],
                "pre_quality": pre_quality,
                "pre_switch": pre_switch,
                "oracle_gap": oracle_delta,
                "changed_actual_starter": int(home_new or away_new),
                "home_actual_change": int(home_new),
                "away_actual_change": int(away_new),
                "has_prior_both": int(bool(expected_h and expected_a)),
                "prior_quality_home": rating(expected_h),
                "prior_quality_away": rating(expected_a),
                "actual_quality_home": rating(observed_h),
                "actual_quality_away": rating(observed_a),
            })

        # Apply box-score data only once the entire target week is projected.
        for box in stats_by_week.get((season, week), []):
            state = career[str(box["player_id"])]
            state[0] += float(box["passing_epa"])
            state[1] += float(box["drops"])

        # Start identities are observed after the game. A future week's
        # feature can use those past identities, never same-week identities.
        for game in slate.to_dict("records"):
            if pd.isna(game["home_score"]) or pd.isna(game["away_score"]):
                continue
            for t, pid in ((game["home_team"], game.get("home_qb_id")),
                           (game["away_team"], game.get("away_qb_id"))):
                if pid is not None and pd.notna(pid):
                    team_starters[str(t)].append(str(pid))
    return pd.DataFrame.from_records(records)


def assess(schedule, boxes):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    elo = predict_regular_season(schedule)
    feat = prior_features(schedule, boxes)
    data = elo.merge(feat, on="game_id", validate="one_to_one")
    data = data[data.pick_result.isin(["Correct", "Incorrect"])
                & data.season.isin(YEARS)].copy()
    data["actual_home"] = (data.pick_result.eq("Correct")
                           == data.predicted_winner.eq(data.home_team)).astype(int)
    data["elo_logit"] = np.log(data.home_probability.clip(1e-8, 1-1e-8)
                               / (1-data.home_probability.clip(1e-8, 1-1e-8)))
    data["pre_quality"] = data["pre_quality"] * 10.
    data["pre_switch"] = data["pre_switch"] * 10.
    data["oracle_gap"] = data["oracle_gap"] * 10.
    candidates = {
        "elo_recalibrated": ["elo_logit"],
        "pregame_last_qb_quality": ["elo_logit", "pre_quality"],
        "pregame_replacement_persistence": ["elo_logit", "pre_quality", "pre_switch"],
        "oracle_actual_starter_gap": ["elo_logit", "pre_quality", "oracle_gap"],
    }
    train = data[data.season.isin(TRAIN)].copy()
    if len(train) < 1000:
        raise ValueError("Training coverage below expected 1000 games")
    fitted = {}
    for name, cols in candidates.items():
        pipe = make_pipeline(StandardScaler(), LogisticRegression(
            C=1.0, max_iter=2000, solver="lbfgs"))
        pipe.fit(train[cols], train.actual_home)
        data[name] = pipe.predict_proba(data[cols])[:, 1]
        fit = pipe.named_steps["logisticregression"]
        fitted[name] = {
            "columns": cols,
            "coef": fit.coef_[0].tolist(),
            "intercept": float(fit.intercept_[0]),
            "scaler_mean": pipe.named_steps["standardscaler"].mean_.tolist(),
            "scaler_scale": pipe.named_steps["standardscaler"].scale_.tolist(),
        }

    def evaluate(d, probcol):
        n = len(d)
        if not n:
            return {"games": 0}
        y = d.actual_home.to_numpy(dtype=float)
        p = d[probcol].to_numpy(dtype=float)
        hit = int(((p >= .5) == (y > .5)).sum())
        return {"games": n, "wins": hit, "losses": n-hit,
                "accuracy_pct": round(100*hit/n, 2),
                "brier": round(float(np.mean((p-y)**2)), 5),
                "logloss": round(float(np.mean(
                    -(y*np.log(np.clip(p, 1e-8, 1))+
                      (1-y)*np.log(np.clip(1-p, 1e-8, 1))))), 5)}

    periods = {"2019-2022 development": TRAIN, "2023-2025 retrospective": EVAL,
               "2026 through available results": (2026,)}
    periods.update({str(year): (year,) for year in YEARS})
    reports = {}
    for label, years in periods.items():
        subset = data[data.season.isin(years)]
        obs = {"games": len(subset),
               "actual_starter_change_games": int(subset.changed_actual_starter.sum()),
               "with_prior_qb_both": int(subset.has_prior_both.sum())}
        groups = {
            "all": subset,
            "actual_changed_starter_oracle_diagnostic":
                subset[subset.changed_actual_starter.eq(1)],
            "same_actual_starters":
                subset[subset.changed_actual_starter.eq(0)],
        }
        for groupname, grp in groups.items():
            stats = {"elo_unmodified": evaluate(grp, "home_probability")}
            for name in candidates:
                stats[name] = evaluate(grp, name)
            obs[groupname] = stats
        reports[label] = obs
    return {"method": {
        "metric": "career prior-game QB passing EPA / (attempts + sacks + 150 pseudo plays), clipped +/-0.45",
        "expected_qb": "last observed starter from completed previous games; not a verified next starter",
        "replacement_proxy": "observed actual upcoming starter; hindsight identity, used only as an oracle upper bound",
        "pregame_model_columns": candidates["pregame_replacement_persistence"],
        "training_seasons": list(TRAIN),
        "no_same_week_leakage_in_performance_metrics": True,
        "future_starter_identity_not_usable_live": True,
        "baseline": "unchanged Sunday Slate NFL-ELO-1.0"},
        "rows": {"player_week_qb": len(boxes), "graded": len(data)},
        "fitted_models": fitted, "results": reports}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="qb_replacement_quality_results.json")
    parser.add_argument("--schedule")
    parser.add_argument("--players")
    args = parser.parse_args()
    sched = (pd.read_csv(args.schedule, low_memory=False) if args.schedule
             else load_schedules())
    for col in ("season", "week", "home_score", "away_score"):
        sched[col] = pd.to_numeric(sched[col], errors="coerce")
    print("Loading quarterback weekly box scores...", flush=True)
    boxes = load_qb_boxes(args.players)
    print("QB rows:", len(boxes), "Schedule rows:", len(sched), flush=True)
    result = assess(sched, boxes)
    output = json.dumps(result, indent=2, allow_nan=False)
    print("QB_REPLACEMENT_RESULT_BEGIN")
    print(output, flush=True)
    print("QB_REPLACEMENT_RESULT_END", flush=True)
    Path(args.output).write_text(output+"\n")


if __name__ == "__main__":
    main()

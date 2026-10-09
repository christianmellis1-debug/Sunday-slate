# Sunday Slate — NFL model validation (Phase 2)

**Model:** `NFL-ELO-1.0` — a transparent straight-up pregame probability baseline, **not** a betting-selection engine.

## Historical evaluation

Data source: nflverse's `nfldata/data/games.csv` schedule and results, checked **October 9, 2026**. Only **regular season games with decisive final scores** count toward accuracy; ties and unplayed games do not.

| Season | Classification | Wins | Losses | Straight-up accuracy | Brier |
| --- | --- | ---: | ---: | ---: | ---: |
| 2019–2022 | Parameter selection | 682 | 368 | 64.95% | 0.2230 |
| 2023 | Out-of-sample | 165 | 107 | 60.66% | 0.2335 |
| 2024 | Out-of-sample | 179 | 93 | 65.81% | 0.2129 |
| 2025 | Out-of-sample | 174 | 97 | 64.21% | 0.2229 |
| **2023–2025** | **Combined holdout** | **518** | **297** | **63.56%** | **0.2231** |
| 2026 through Oct 9 | Preliminary / incomplete | 42 | 23 | 64.62% | 0.2312 |
| 2023–2026 to date | Includes incomplete season | 560 | 320 | 63.64% | 0.2237 |

Brier measures the mean squared error of forecast probabilities versus game outcomes (lower is better). Log loss is computed in the reproducible CLI, along with all other metrics.

## Model features

- Team-strength Elo ratings, initialized to 1500, updated from prior wins/losses.
- Margin-of-victory scaling (bounded at a 28-point difference).
- Home-field bonus, disabled for games with neutral-site classification.
- Rest difference in days, clipped to ±7.
- Rating regression toward average between seasons.

**Fixed parameters selected exclusively on 2019–2022:** K=36, home adjustment=30 Elo, retention=0.75, probability temperature=0.8, rest adjustment=3 Elo per day, MOV weight=0.7. The backtest runs from 2014, providing prior-season warmup history. Selection was a finite grid search; there is still overfitting risk due to tuning and the size of the historical sample.

**Leakage prevention:** All weekly game probabilities are computed before processing *any* final results from that week. Ratings update once the complete week's predictions have been recorded. The same logic runs in the live dashboard and the backtesting CLI. Future scores cannot modify earlier-week estimates; the test suite checks this.

## How to reproduce

```bash
pip install -r requirements.txt
python -m backtests.run_backtest --output model_validation.json
```

To use a pinned local copy of the schedule, download the nflverse source file and pass `--csv path/to/games.csv`. The live feed may be updated after this research snapshot, so 2026 numbers will change and occasional corrections may change historical counts.

## Explicit limitations

1. No player- or quarterback-level adjustments, injury feeds, EPA/success-rate features, forecast weather, or market odds in this baseline.
2. Results are **not ATS records, profitability, betting confidence, or proof that a particular spread or moneyline is favorable**.
3. Probabilities are baseline estimated win chances; their calibration remains imperfect. Do not interpret them as a guarantee.
4. Postseason predictions are intentionally disabled because this validation covers the regular season.
5. Retrospective 2019–2022 is **training**, not an independent test; the 2023–2025 holdout should not be retuned using those years if we want to preserve its independence.

Future upgrades should be evaluated via rolling-origin testing on pregame feature snapshots (including injuries and verified odds), compared to this frozen baseline using Brier, log loss, accuracy, and, only with verifiable contemporaneous odds, betting ROI.

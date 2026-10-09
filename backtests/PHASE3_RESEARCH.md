# Sunday Slate — Phase 3: NFL matchup and value research

## Implementation shipped

Phase 3 adds a **research layer**, not unverified betting picks. The straight-up NFL-ELO-1.0 baseline, validated in Phase 2, remains frozen. We did NOT blend new inputs into an untested model or pretend that an EPA feature improves probabilities without backtesting it.

**Advanced matchup data:** prior regular-season weeks only, aggregated from nflverse weekly team stats. Offensive passing/rushing EPA per pass attempt/carry; opponent EPA allowed is aggregated from the opponent's actual box score in the same previous game. This is an approximation, not corrected per-dropback or opponent-adjusted EPA. When columns/history are absent, display “Unavailable,” never 0.

**Quarterbacks:** player-level weekly stats, trailing four previous weeks; most-used passer by pass attempts (YPA and interceptions). It does NOT establish the upcoming starter or injury status.

**Injuries:** Not integrated into live predictions. The nflverse historical injury feed became unavailable after 2024, so using it for 2025/2026 would be misleading. We will not infer that a player is healthy just because the injury feed lacks a row. A current, auditable provider and kickoff-time snapshots are needed.

**Market research:** odds are sourced from home_moneyline/away_moneyline in the public nflverse schedule, and are clearly marked *reference prices*. They are NOT certified live, time-stamped sportsbook prices or verified DraftKings offers. Both valid sides must exist; no single-sided markets or invalid spreads. Moneyline probabilities normalize the overround (vig) before comparison.

## Retrospective reference moneyline sensitivity (not realized earnings)

Using the frozen NFL-ELO-1.0 model and NFLverse's historical schedule reference lines, 2023–2025 decisive regular-season games.

| Research screen | 2023–2025 selections | W–L | Historical units at 1 unit risk | Reference-price ROI |
| --- | ---: | --- | ---: | ---: |
| >=3pp no-vig edge, >=58% model, odds -350 to +250 | 148 | 79–69 | -13.03 | -8.80% |
| >=5pp no-vig edge, >=60% model, odds -300 to +200 | 93 | 50–43 | -3.29 | -3.54% |
| >=8pp no-vig edge, >=60% model, odds -300 to +200 | 63 | 34–29 | +1.34 | +2.13% |

The **default on-screen exploratory screen is 5pp, >=60%, -300 to +200**, which **did not show positive historical ROI**. By year:
- 2023: 15–14, -0.28 units, -0.96% ROI
- 2024: 24–14, +4.96 units, +13.04% ROI
- 2025: 11–15, -7.96 units, -30.63% ROI

An 8pp screen was checked post hoc and has only 63 selections over three seasons. Its +2.13% *reference price* result is not robust proof of betting advantage. We deliberately did not convert it into an “official value pick” rule.

### Critical backtest limitations

- Historical schedule moneylines may be reference or closing prices; timestamps and bookmaker provenance are unverified. It is NOT known whether these prices were actually available before a given game's kickoff.
- This is a retrospective sensitivity check only, not a credible time-stamped execution backtest; the percentages MUST NOT be used as an expected ROI, actual bettor returns, or future bet recommendation.
- There is selection bias from reviewing several thresholds. Future optimization must use a new, independent walk-forward holdout, preserving all pregame features and quoted sportsbook odds before kickoff.
- The comparison does not adjust for line movement, bet limits, platform fees, stake sizing, or source corrections. A 5pp “edge” is not a profitability guarantee.
- No ATS/totals or parlay grading has been implemented. No sportsbook data is authenticated.

## Reproduction

```bash
pip install -r requirements.txt
python -m backtests.phase3_value_research
# Or with a locally downloaded nflverse schedules file
python -m backtests.phase3_value_research --csv games.csv
```

The above analysis was computed from the publicly available NFLverse `nfldata/data/games.csv` schedule snapshot on **October 9, 2026**. Corrections to past games/odds may change results.

## Proposed prerequisite before official betting tiers

1. Record true pre-kickoff (ideally timestamped) sportsbook odds, then build an immutable weekly selection ledger.
2. Validate strong football covariates (quarterback availability, opponent-adjusted EPA, injuries, rest, weather) through prior-week training and chronological untouched seasons.
3. Compare Brier, log loss, straight-up accuracy, and betting ROI to the frozen Phase 2 baseline.
4. Keep incomplete odds/health feeds unpublished; permit *no selection* rather than filling a target card.

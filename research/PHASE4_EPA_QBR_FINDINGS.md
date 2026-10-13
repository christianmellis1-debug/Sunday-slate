# Sunday Slate — Phase 4 opponent-adjusted EPA and quarterback QBR experiments

**Date:** October 13, 2026  
**Status:** Research only; NFL-ELO-1.0 production predictions and user-facing waterfall are unchanged.  
**Source:** nflverse regular-season schedules and weekly team EPA via nflreadpy, plus ESPN Total QBR weekly release.  
**Reproducible run:** [EPA/QBR GitHub Action](https://github.com/christianmellis1-debug/Sunday-slate/actions/runs/38416416444) · [Research script](model_epa_qbr_study.py).

## Objective and study design

We want **>66% full-slate straight-up accuracy**, not an artificially high win rate from filtering down to a small subset of games. This study compares Elo and combinations of two new signals:

- **EPA:** Earlier weeks' offensive passing/rushing EPA per passing attempt/rush carry and defensive EPA allowed from the prior opponents' respective play-level aggregates. An approximate opponent-strength adjustment removes half the estimated pregame opponent-strength component, with a games/(games+3) shrinkage factor. This is **not** a fully specified play-by-play two-way opponent-adjusted EPA regression and should not be advertised as one.
- **Quarterback:** ESPN Total QBR over the preceding four weeks, plays-weighted for each team's highest-usage QB. This is a **prior most-used-passer proxy**, **not confirmed expected starter** and not guaranteed comparable to ESPN's published rolling QBR.
- **Recent scoring:** Preweek last-four-game scoring margins with season-local reset and finite-history shrinkage.

The research code computes all inputs at the start of the target NFL week, then updates EPA records only after all forecasts for that week have been created. **No results from target or later weeks** enter their predictions. Logistic coefficients are trained only on **2019–2022**. The 2023–2025 period has been examined repeatedly in previous investigations and is **not a pristine untouched holdout**. 2026 is a preliminary evolving check.

Sources loaded: **3,900 weekly team-EPA lines**, **10,444 weekly ESPN QBR rows**, **1,943 graded 2019–2026 games**. The 2023–2025 evaluation has **815 decisive games**; the available 2026 snapshot has **78**. Both prior-QBR proxies were available in 734/815 of the 2023–2025 comparisons.

## Full-slate results

| Research model | 2023–2025 (815 games) | 2026 preliminary (78 games) |
| --- | ---: | ---: |
| Current NFL-ELO-1.0 | **518–297 · 63.6%** | **52–26 · 66.7%** |
| Elo + raw offensive/defensive EPA | 525–290 · 64.4% | 50–28 · 64.1% |
| Elo + approximate opponent-adjusted EPA | 527–288 · 64.7% | 50–28 · 64.1% |
| Elo + prior QB QBR proxy | 530–285 · 65.0% | 49–29 · 62.8% |
| Elo + adjusted EPA + QBR proxy | 528–287 · 64.8% | 50–28 · 64.1% |
| Elo + recent four-game scoring margin | 536–279 · 65.8% | 50–28 · 64.1% |
| **Elo + recent form + raw EPA** | **545–270 · 66.9%** | **49–29 · 62.8%** |
| **Elo + recent form + adjusted EPA** | **545–270 · 66.9%** | **49–29 · 62.8%** |
| Elo + recent form + QBR proxy | 529–286 · 64.9% | 47–31 · 60.3% |
| Elo + recent form + adjusted EPA + QBR | 541–274 · 66.4% | 49–29 · 62.8% |

Brier (lower is better), 2023–2025: Elo **0.22309**; recent form **0.22199**; recent form + adjusted EPA **0.22190**. 2026: Elo **0.22331**; recent form + adjusted EPA **0.22278**. Small improvements in Brier do **not** offset the observed accuracy decline.

## Year-by-year: the strongest retrospective combination

| Year | Baseline Elo | Recent form + adjusted EPA |
| --- | ---: | ---: |
| 2023 | 165–107 · 60.7% | 173–99 · 63.6% |
| 2024 | 179–93 · 65.8% | 196–76 · 72.1% |
| 2025 | 174–97 · 64.2% | 176–95 · 64.9% |
| **2023–2025** | **518–297 · 63.6%** | **545–270 · 66.9%** |
| **2026 so far** | **52–26 · 66.7%** | **49–29 · 62.8%** |

**17 of the 27 net additional correct retrospective picks occurred in 2024.** The QB feature did not add predictive value on top of the strongest recent-form + EPA combination. The comparison covered several alternative models and may be optimistic because of repeated testing.

## Decision

**Do not deploy** the latest variant as the primary NFL forecast. It beat 66% retrospectively, but it has not surpassed production Elo on the separate preliminary 2026 evaluation. The historical sources are retrospectively assembled and could have been revised since their respective kickoff dates.

Keep the official model and research tiers unchanged. Freeze a candidate scoring-form + EPA model with fixed weights for the next prospective slate and archive its pre-kickoff probabilities. Pursue independently verified **pregame starting QB and injury data** before relying on quarterback adjustments. For betting-value and ATS tiers, use only time-stamped pregame **DraftKings** prices, which are not available in this test.

Reproduce with:

```bash
python -m research.model_epa_qbr_study --output epa_qbr_model_results.json
```

The automatic research workflow saves the full JSON as a 30-day Actions artifact. No sportsbook prices, spreads, or betting-profit calculations were used.

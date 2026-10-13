# Sunday Slate — Phase 4 research track (NOT DEPLOYED)

Status: **RESEARCH ONLY**. Production prediction and coaching signals remain unchanged.

## Baseline and goals

- Current model: **NFL-ELO-1.0**, trained/tuned on 2019–2022, evaluated on 2023–2025: **518–297 (63.56% straight-up)**.
- Target: **>66% full-slate straight-up accuracy** on a future, genuinely uninspected evaluation period, without worsened probability calibration.
- Distinct objective: Build a **mutually exclusive selective research waterfall**, targeting reproducible and useful accuracy by bucket. Coverage and calibration must be reported alongside win rate. High selective hit rates do not imply profitability.

## Reproducible Phase 4 experiment

Run:

\`\`\`bash
python -m backtests.experimental_research --csv path/to/pinned-nflverse-games.csv --output phase4_results.json
\`\`\`

Without \`--csv\`, the runner uses the installed nflreadpy schedule loader and fetches the current published historical schedule.

The new module \`backtests/experimental_research.py\` reuses production Elo outputs, but only as inputs to a **parallel diagnostic model**. It does not write to the app or change any predictions.

- Recent-form feature: home team last 4 completed regular-season scoring margins minus away team last 4 scoring margins, with a two-point non-neutral home context adjustment, multiplied by \`min(prior games)/(min(prior games)+4)\`, divided by 10.
- Regular-season scoring history resets every season. Elo itself retains its existing offseason-regression behavior.
- One *entire* schedule week is snapshotted before any of that week's outcomes update Elo or scoring features.
- Fixed, deterministic logistic calibration: Elo rating difference/100 plus the recent-form score feature, with a small ridge penalty. Fit on **2019–2022 only**. The code does not select its parameters using 2023+ outcomes.
- The 2023–2025 period has *already been inspected* during this investigation and is no longer a pristine independent holdout; report it as retrospective.
- The 2026 period is an evolving preliminary test. Do not re-fit the model each time a new weekly outcome is seen.

### Prior research estimates (subject to rerun with pinned inputs)

| Variant | 2023–2025 straight-up | 2026 through available snapshot |
|---|---|---|
| Production Elo | 518–297 (63.6%) | 52–26 (66.7%) |
| Elo + recent four-game margin | 537–278 (65.9%) | 50–28 (64.1%) |

The above numbers describe the preliminary research reconstruction. Use the CLI's pinned snapshot and its computed coefficients for **final reproducible results**; don't claim accuracy has exceeded 66% consistently.

## Candidate tiers

Each matchup is assigned to **one** category, first-match-wins. Tiers grade the *unmodified Elo-selected winner*, and use PPG only as an agreement signal.

1. **Tier 1: Elite Rating** — Elo confidence >=75%.
2. **Tier 2: Double Confirmation** — >=3 games played by both teams, Elo >=60%, pregame adjusted PPG model agrees, projected PPG margin >=7.
3. **Tier 3: Solid Consensus** — >=3 games played by both teams, Elo >=60%, pregame PPG model agrees, margin below 7.
4. **Tier 4: Uncertain** — every remaining matchup.

Previous exploratory 2023–2025 partition: Tier 1 **62–14 (81.6%)**, Tier 2 **47–16 (74.6%)**, Tier 3 **139–61 (69.5%)**, remaining **270–206 (56.7%)**.

**Important:** Tier 1 and Tier 2 might overlap *without* the defined waterfall order. Always apply this specific ordering; do not combine overlapping tier results or characterize high confidence as guaranteed winners. These are not betting selections.

## Research priorities after reproducible validation

1. **Opponent-adjusted efficiency.** nflreadpy's weekly team stats include passing and rushing EPA-related columns; identify denominator consistency and ensure that all opponent rows are matched to past weeks. Compare offense-vs-defense matchup efficiency with Elo and scoring features. A game-level input must never include its own final box score.
2. **Quarterback availability and quality.** nflreadpy exposes historical weekly player stats and rosters; quarterback rolling passing EPA/YPA and snap usage can be tested. Box-score usage alone does **not** verify the next game's starter, so absent pregame injury/start-status history must remain **unknown**, not inferred as known.
3. **Out-of-sample discipline.** If thresholds or variables are selected using 2023–2025, reserve later weeks/seasons or use nested rolling-origin testing for validation. Keep a frozen version of each algorithm and weekly prediction snapshot.
4. **Production migration gate.** Require consistent improvement across seasons, confidence calibration (Brier/log loss), stable missing-data handling, sample-size reporting, and no latency regression on free Streamlit hosting.
5. **DraftKings-only betting analysis.** No ATS or ROI claims without timestamped pre-kickoff DraftKings prices. Market lines never enter this Phase 4 historical test.

Sources: nflverse game schedules/results; nflreadpy load functions and team/player weekly statistics. These are independent football signals, not official NFL predictions.

# Sunday Slate 🏈

An independent NFL prediction and matchup analytics app on Streamlit Community Cloud, developed separately from Saturday Forecast.

## Phase 1 — Schedule foundation

- Weekly NFL games including Thursday–Monday, international games and postseason schedule browsing
- Central Time kickoff display, final scores when available, team logos, and responsive dark matchup cards
- Search and filters for season, stage, week, day, teams and upcoming games
- Score and prior-week statistics from nflverse with data caching
- Automated offline smoke tests and defensive handling of unavailable feeds

## Phase 2 — NFL straight-up probability model (implemented)

- **NFL-ELO-1.0** winner predictions and estimated win chances on regular-season matchup cards
- Historical results-based team ratings, home-field effects, rest-day differences and bounded point-margin updating
- Pregame weekly snapshot logic with same-week/future-result leakage protection
- Scored model picks, season record, win percentage, and model validation disclosures
- **2023–2025 out-of-sample record: 518–297 (63.6%)**, versus **515–300 (63.2%)** for a simple Elo baseline; not ATS or market ROI
- Brier score and log loss reporting, plus baseline comparison and reproducible backtesting
- Full methodology and limits in [backtests/MODEL_VALIDATION.md](backtests/MODEL_VALIDATION.md)
- An automated unit-test workflow; research scripts do not run automatically on every deploy

## Phase 3 — Advanced matchup & market research (implemented)

- Prior-week offensive EPA per passing attempt and rushing carry
- Defensive EPA-allowed comparisons derived from earlier opposing team boxes
- Recent (four previous weeks) highest-volume quarterback passer summaries, **not claimed as confirmed starters**
- DraftKings-only pregame moneylines and spreads via TheRundown (private free-tier API key required; five-minute delay). No alternative-book or nflverse odds fallback.
- **Value Research** filter for unverified experimental screen matches, explicitly **not recommended bets**
- Historical reference-price backtests remain in research code, but are no longer presented as DraftKings results. There is no verified DraftKings historical ROI.
- [Phase 3 research methodology and limitations](backtests/PHASE3_RESEARCH.md)
- [Reproducible Phase 3 reference price sensitivity checks](backtests/phase3_value_research.py)

**DraftKings Coaching Trends (research-only flags):** Matchup cards highlight **Ben Johnson Special** (his team favored by 0.5–3), **Schottenheimer Favorite** (Dallas favored by at least 0.5), and **Stefanski Mid-Range Favorite** (his team favored by 3.5–7). Each is available as a filter. The app requires a positive DraftKings-only feed match (affiliate ID 19), never invents a missing line, and never uses historical nflverse odds to trigger a flag. Historical cover rates are exploratory rather than validated betting edges; flags never change Elo picks.

**Game-week injury reports** are shown only when the current NFLverse feed contains a dated report-status record from the selected week before kickoff. Source unavailability or missing players never implies health or confirmed availability. No injury input changes the Phase 2 model.

### Not yet implemented

A fully audited current injury feed, a verified historical DraftKings closing-line archive, validated profitable betting selection tiers, player/QB injury adjustments, weather factors, parlays, bet tracker or postseason win-probability model. **A model pick or positive market difference is not a recommendation.**

## Deployment (free)

1. Open https://share.streamlit.io and create or edit an app.
2. Select repository **christianmellis1-debug/Sunday-slate**, branch **main**, entrypoint **app.py**.
3. Deploy on Streamlit Community Cloud with Python 3.11.
4. For **personal/internal testing**, obtain a no-credit-card API key from [TheRundown](https://auth.therundown.io/signup/) (Free: DraftKings pregame prices delayed by five minutes).
5. In Streamlit app settings > **Secrets**, add `THERUNDOWN_API_KEY = "YOUR_KEY"`. Do not commit or display the key.
6. The app uses nflverse for schedules and scores only. Betting lines and coaching signals use the DraftKings affiliate ID exclusively; absent/blocked/unmatched DraftKings quotes are shown as unavailable. No cross-book fallback is allowed.
7. **Licensing:** The provider's Free plan is for testing, not unrestricted commercial end-user odds display. Confirm display rights before making a public/commercial odds-display service.

Local development:

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Regression suite:

```bash
python -m pip install pytest
python -m pytest -q
```

Reproduce historic holdouts:

```bash
python -m backtests.run_backtest --output model_validation.json
```

## Phase 4 — NFL model improvement research (experimental, not deployed)

- **Goal:** Improve full-slate straight-up accuracy beyond 66% while separately building reliable, mutually exclusive research tiers. No unverified betting ROI claims.
- **Prototype:** [Offline reproducible research runner](backtests/experimental_research.py), with [methodology and validation cautions](backtests/PHASE4_RESEARCH.md). It freezes scoring history at each week's start and fits only on 2019–2022, using the unmodified current Elo model.
- **First target:** A parallel logistic model using the prior four games' scoring margins. Preliminary retrospective 2023–2025: **537–278 (65.9%)**, versus **518–297 (63.6%)** production Elo. Preliminary 2026 through the available Week 5 snapshot: **50–28 (64.1%)**, versus **52–26 (66.7%)** Elo. **Not approved for production.**
- **Selective tiers:** Elo >=75%; Elo 60%+ and PPG agreement with margin >=7; Elo 60%+ with PPG agreement; remaining/uncertain. Categories are exclusive and assigned in that order. These tiers are not official picks or recommendations.
- **Next testing tracks:** Preweek, opponent-adjusted rushing/passing efficiency, weekly QB production and independently verified starter context, then rolling-origin evaluation. 2023–2025 has already been inspected and is no longer an untouched holdout.

Run the research independently (the app does not load this at startup):

\`\`\`bash
python -m backtests.experimental_research --csv /path/to/pinned-nflverse-games.csv --output phase4_results.json
\`\`\`

## Data and licensing

Uses [nflverse](https://github.com/nflverse) and [nflreadpy](https://github.com/nflverse/nflreadpy) for public football data. Most nflverse datasets are CC BY 4.0; nflreadpy is MIT. Logos are owned by the respective teams. There are no paid hosting requirements; the optional DraftKings feed has a free delayed pregame tier suitable for personal testing, not public commercial display. Historical reports are snapshots and can change if sources correct past games.

## Next phase

Secure timestamped pre-kickoff sportsbook prices and a current injury feed, backtest opponent-adjusted EPA and quarterback availability against frozen baseline without same-week data leakage, then consider official betting tiers *only* with credible prospective evidence.

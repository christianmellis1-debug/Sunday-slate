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

### Not yet implemented

QB-level adjustments, verified injury/weather inputs, sportsbook odds, betting value picks and tiers, parlay finder, bet tracker or postseason win-probability model. **A model pick is not a betting recommendation.** Past win rates are not forecasts of future accuracy.

## Deployment (free)

1. Open https://share.streamlit.io and create or edit an app.
2. Select repository **christianmellis1-debug/Sunday-slate**, branch **main**, entrypoint **app.py**.
3. Deploy on Streamlit Community Cloud with Python 3.11.
4. The app fetches the updated nflverse schedule; scores are not guaranteed to be live.

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

## Data and licensing

Uses [nflverse](https://github.com/nflverse) and [nflreadpy](https://github.com/nflverse/nflreadpy) for public football data. Most nflverse datasets are CC BY 4.0; nflreadpy is MIT. Logos are owned by the respective teams. There are no paid hosting or paid data requirements for Phases 1–2. Historical reports are snapshots and can change if sources correct past games.

## Next phase

Validate additional pregame predictors (EPA, QB status, injuries, weather), perform out-of-sample comparative backtesting, and only then begin proposing NFL-specific odds-based filters and betting recommendations.

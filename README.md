# Sunday Slate 🏈

An independent NFL schedules and pregame matchup dashboard, built in Streamlit Community Cloud. This repository is separate from Saturday Forecast.

## Phase 1

- Weekly NFL games across Thursday–Monday, international games and playoffs
- Central Time kickoff display, score and status when recorded
- NFL team logos and dark responsive matchup cards
- Filters for season, stage, week, day, team and upcoming games
- No-lookahead comparison of prior-week records, PPG, opponent PPG, passing and rushing yards/game
- Cached nflverse feeds and graceful failure handling
- Automated unit tests and offline Streamlit smoke test

**Not yet implemented:** NFL win-probability model, confidence, value picks, sportsbook odds, betting tiers, parlays, weather, injury feeds or betting tracker. No fabricated model picks.

## Deploy (free)

1. Open https://share.streamlit.io and choose **New app**.
2. Select **christianmellis1-debug/Sunday-slate**, branch **main**, main file **app.py**.
3. Deploy on Streamlit Community Cloud. Use Python 3.11 if prompted.
4. Schedule updates come from nflverse and are not a real-time scoreboard.

Local run:
```bash
pip install -r requirements.txt
streamlit run app.py
```

Tests (pytest is a development dependency):
```bash
pip install pytest
python -m pytest -q
```

## Data/attribution

Uses nflreadpy and nflverse for schedules, team statistics and branding. Most nflverse datasets are CC BY 4.0. nflreadpy is MIT-licensed. Logos belong to their respective teams. Scores may lag; final means both score fields have populated. No secrets or paid services required in Phase 1.

## Next

Develop, calibrate and backtest an NFL-specific prediction engine using chronological out-of-sample evaluations before introducing recommended bets.
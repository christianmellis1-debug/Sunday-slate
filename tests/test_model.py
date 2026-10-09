import pandas as pd
import pytest

from sunday_slate.model import DEFAULT, VERSION, predict_regular_season, probability, rationale, summary
from sunday_slate.ui import prediction_panel


def games():
    return pd.DataFrame([
        dict(game_id='2025_01_A_B', season=2025, week=1, game_type='REG', home_team='B', away_team='A', home_score=21, away_score=10, location='Home', home_rest=7, away_rest=7),
        dict(game_id='2025_01_C_D', season=2025, week=1, game_type='REG', home_team='D', away_team='C', home_score=7, away_score=17, location='Home', home_rest=7, away_rest=7),
        dict(game_id='2025_02_A_D', season=2025, week=2, game_type='REG', home_team='D', away_team='A', home_score=None, away_score=None, location='Neutral', home_rest=7, away_rest=7),
        dict(game_id='2025_03_B_C', season=2025, week=3, game_type='REG', home_team='C', away_team='B', home_score=None, away_score=None, location='Home', home_rest=4, away_rest=8),
        dict(game_id='2025_19_B_C', season=2025, week=19, game_type='WC', home_team='C', away_team='B', home_score=18, away_score=20, location='Home', home_rest=7, away_rest=7),
    ])


def test_same_week_forecasts_frozen_before_results():
    old = games()
    baseline = predict_regular_season(old)
    changed = old.copy()
    changed.loc[0, ['home_score','away_score']] = [0, 60]
    altered = predict_regular_season(changed)
    for gid in ('2025_01_A_B', '2025_01_C_D'):
        b = baseline.set_index('game_id').loc[gid]
        a = altered.set_index('game_id').loc[gid]
        assert a.home_probability == pytest.approx(b.home_probability)
    assert (altered.set_index('game_id').loc['2025_02_A_D'].home_probability
            != baseline.set_index('game_id').loc['2025_02_A_D'].home_probability)


def test_future_results_do_not_change_earlier_predictions():
    old = games()
    new = old.copy()
    new.loc[3, ['home_score','away_score']] = [55, 0]
    a, b = [predict_regular_season(frame).set_index('game_id') for frame in (old, new)]
    for gid in ('2025_01_A_B','2025_01_C_D','2025_02_A_D','2025_03_B_C'):
        assert a.loc[gid].home_probability == pytest.approx(b.loc[gid].home_probability)


def test_neutral_field_and_rest_adjustments():
    output = predict_regular_season(games()).set_index('game_id')
    assert output.loc['2025_02_A_D'].home_field_elo == 0
    assert output.loc['2025_03_B_C'].rest_elo == pytest.approx(-12)
    assert output.loc['2025_01_A_B'].home_field_elo == DEFAULT.home_advantage


def test_ties_excluded_from_accuracy():
    frame = games()
    frame.loc[0, ['home_score','away_score']] = [17,17]
    r = predict_regular_season(frame).set_index('game_id')
    assert r.loc['2025_01_A_B'].pick_result == 'Push'
    assert r.loc['2025_01_A_B'].pick_correct is None
    assert summary(r.reset_index())['games'] == 1


def test_excludes_postseason_pending_validation():
    frame = predict_regular_season(games())
    assert len(frame) == 4
    assert '2025_19_B_C' not in set(frame.game_id)


def test_missing_and_duplicate_games_fail_closed():
    frame = games()
    with pytest.raises(ValueError, match='duplicate'):
        predict_regular_season(pd.concat([frame,frame.iloc[[0]]], ignore_index=True))
    with pytest.raises(ValueError, match='Missing model columns'):
        predict_regular_season(frame.drop(columns=['home_team']))


def test_probability_symmetric_bounded():
    assert probability(0) == pytest.approx(.5)
    assert probability(50) + probability(-50) == pytest.approx(1)
    assert 0 < probability(-15000) < .5
    assert .5 < probability(15000) < 1


def test_grading_and_probability_metrics():
    output = predict_regular_season(games()).set_index('game_id')
    assert output.loc['2025_02_A_D'].pick_result == 'Pending'
    assert output.loc['2025_01_A_B'].pick_result == 'Correct'
    assert output.loc['2025_01_C_D'].pick_result == 'Incorrect'
    report = summary(output.reset_index())
    assert report['games'] == 2 and report['wins'] == 1 and report['losses'] == 1
    assert 0 < report['brier'] < 1 and 0 < report['logloss'] < 2
    assert set(output.model_version) == {VERSION}


def test_card_rationale_is_grounded_and_escaped():
    result = predict_regular_season(games()).set_index('game_id').loc['2025_02_A_D']
    assert 'injuries' in rationale(result)
    html = prediction_panel(result)
    assert 'Model winner:' in html
    assert 'Research probability' in html

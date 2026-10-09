"""Regression coverage for the independent rushing EPA research adapter."""
import pandas as pd
import pytest

from research.run_defense_rush_epa import load_rush_epa, choose, make_report
from research.run_defense_rush import THRESHOLDS


def _epa_inputs():
    return pd.DataFrame([
        dict(season=2025, week=1, game_id="2025_01_A_B",
             season_type="REG", team="A", opponent_team="B",
             rushing_yards=1000, rushing_epa=-12, carries=20),
        dict(season=2025, week=1, game_id="2025_01_A_B",
             season_type="REG", team="B", opponent_team="A",
             rushing_yards=1, rushing_epa=9, carries=30),
    ])


def test_epa_adapter_uses_epa_not_yards(tmp_path):
    path=tmp_path/"data.csv"
    _epa_inputs().to_csv(path,index=False)
    data=load_rush_epa(str(path)).set_index("team")
    assert data.loc["A", "rushing_yards"] == -12
    assert data.loc["B", "rushing_yards"] == 9
    assert data.loc["A", "rushing_yards"]/data.loc["A", "carries"] == pytest.approx(-.6)
    assert data.loc["B", "rushing_yards"]/data.loc["B", "carries"] == pytest.approx(.3)


def test_missing_epa_column_is_rejected(tmp_path):
    path=tmp_path/"bad.csv"
    _epa_inputs().drop(columns="rushing_epa").to_csv(path,index=False)
    with pytest.raises(ValueError, match="rushing_epa"):
        load_rush_epa(str(path))


def test_overrides_must_be_chosen_from_discovery_only():
    bad=[{
        "quantile": .25,
        "signal_winner":{"games": 80},
        "signal_overrides_elo":{"games": 20},
        "net_changes_if_override": -6,
    }]
    strong=[{
        "quantile": .25,
        "signal_winner":{"games": 80},
        "signal_overrides_elo":{"games": 20},
        "net_changes_if_override": 7,
    }]
    selected, validation = choose(bad, strong)
    assert selected is None and validation is None
    selected, validation = choose(strong, bad)
    assert selected == {"quantile": .25, "net_changes": 7}
    assert validation == bad[0]


def test_thresholds_are_prespecified():
    assert THRESHOLDS == (.2, .25, 1/3, .4)

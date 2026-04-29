import os

from simulation_core import get_default_params, run_simulation


def test_default_parallel_backend_is_threading_for_local_stability(monkeypatch):
    monkeypatch.delenv("SIMMED_JOBLIB_BACKEND", raising=False)
    params = get_default_params()
    df, df_reg = run_simulation(params, n_runs=4, n_years=1, base_seed=11)
    assert len(df) == 8
    assert len(df_reg) == 64


def test_worker_count_can_be_limited_by_environment(monkeypatch):
    monkeypatch.setenv("SIMMED_MAX_WORKERS", "1")
    monkeypatch.setenv("SIMMED_JOBLIB_BACKEND", "threading")
    params = get_default_params()
    df, df_reg = run_simulation(params, n_runs=3, n_years=1, base_seed=21)
    assert sorted(df["run_id"].unique()) == [0, 1, 2]
    assert len(df_reg) == 48

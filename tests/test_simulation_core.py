from simulation_core import (
    MODEL_VERSION,
    aggregate_kpis,
    build_scenario_manifest,
    get_default_params,
    run_scenario,
    run_simulation,
)


def test_simulation_core_runs_small_scenario():
    params = get_default_params()
    df, df_reg = run_simulation(params, n_runs=2, n_years=2, base_seed=123)
    assert len(df) == 2 * 3
    assert len(df_reg) == 2 * 16
    agg = aggregate_kpis(df)
    assert int(agg.iloc[-1]["jahr"]) == 2028
    assert "gkv_saldo_mean" in agg.columns


def test_run_scenario_agent_summary_and_unknown_parameters():
    result = run_scenario({"medizinstudienplaetze": 9000}, n_runs=2, n_years=1, seed=7)
    assert result["model_version"] == MODEL_VERSION
    assert result["parameter_changes"] == {"medizinstudienplaetze": 9000}
    assert result["regional_rows"] == 32
    assert result["scenario_id"] == result["manifest"]["scenario_id"]
    assert result["manifest"]["schema_version"] == "simmed-scenario-manifest-v1"

    try:
        run_scenario({"does_not_exist": 1}, n_runs=1, n_years=1, seed=1)
    except ValueError as exc:
        assert "does_not_exist" in str(exc)
    else:
        raise AssertionError("unknown parameter should raise ValueError")


def test_medical_study_places_halving_creates_delayed_capacity_and_burnout_pressure():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    df, _ = run_simulation(params, n_runs=30, n_years=15, base_seed=42)
    agg = aggregate_kpis(df)

    start = agg.iloc[0]
    year_1 = agg.iloc[1]
    year_6 = agg[agg["jahr"] == 2032].iloc[0]
    final = agg.iloc[-1]

    assert year_1["aerzte_pro_100k_mean"] > start["aerzte_pro_100k_mean"] * 0.90
    assert year_6["aerzte_pro_100k_mean"] < start["aerzte_pro_100k_mean"] * 0.85
    assert final["wartezeit_fa_mean"] > start["wartezeit_fa_mean"]
    assert final["burnout_rate_mean"] >= start["burnout_rate_mean"]


def test_scenario_manifest_is_reproducible_and_provenance_rich():
    changes = {"medizinstudienplaetze": 9000, "telemedizin_rate": 0.12}
    manifest_a = build_scenario_manifest(changes, n_runs=5, n_years=12, seed=99, generated_at="2026-01-01T00:00:00+00:00")
    manifest_b = build_scenario_manifest(dict(reversed(list(changes.items()))), n_runs=5, n_years=12, seed=99, generated_at="2026-02-01T00:00:00+00:00")
    assert manifest_a["scenario_id"] == manifest_b["scenario_id"]
    assert manifest_a["model_version"] == MODEL_VERSION
    assert manifest_a["reproducibility"]["manifest_endpoint"] == "POST /scenario-manifest"
    changed = {item["key"]: item for item in manifest_a["changed_parameters"]}
    assert changed["medizinstudienplaetze"]["source_ids"]
    assert changed["medizinstudienplaetze"]["evidence_grade"] == "A"
    assert "6+" in " ".join(manifest_a["model_caveats"])

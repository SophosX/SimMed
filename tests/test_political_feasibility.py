from political_feasibility import RUBRIC_VERSION, assess_political_feasibility


def test_feasibility_rubric_explains_known_levers_plainly():
    result = assess_political_feasibility({"medizinstudienplaetze": 9000, "telemedizin_rate": 0.15})

    assert result["rubric_version"] == RUBRIC_VERSION
    assert result["status"] == "explanation_only_not_validated_forecast"
    assert result["lever_notes"]
    notes = {note["key"]: note for note in result["lever_notes"]}
    assert "medizinstudienplaetze" in notes
    assert "Telemedizin" in notes["telemedizin_rate"]["label"]
    assert "11–13+" in notes["medizinstudienplaetze"]["implementation_lag"]
    assert notes["medizinstudienplaetze"]["likely_blockers"]
    assert "Strategie-Modus" in result["next_strategy_mode_step"]


def test_feasibility_rubric_handles_unknown_parameters_safely():
    result = assess_political_feasibility({"unknown_policy": 1})

    assert result["category"] == "noch nicht bewertet"
    assert result["lever_notes"] == []
    assert "keine politische Umsetzbarkeitsregel" in result["summary"]

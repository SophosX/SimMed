from data_sources import DATA_SOURCES, list_sources, sources_for_parameter
from parameter_registry import PARAMETER_REGISTRY, evidence_summary, list_parameters


def test_data_sources_have_required_metadata():
    assert "destatis_genesis" in DATA_SOURCES
    for source in DATA_SOURCES.values():
        assert source.id
        assert source.name
        assert source.authority
        assert source.evidence_grade in {"A", "B", "C", "D", "E"}
        assert source.parameters
        assert source.access


def test_parameter_registry_sources_exist_and_ranges_valid():
    assert "medizinstudienplaetze" in PARAMETER_REGISTRY
    for spec in PARAMETER_REGISTRY.values():
        assert spec.source_ids
        assert spec.evidence_grade in {"A", "B", "C", "D", "E"}
        assert spec.data_status in {"aus_daten", "annahme"}
        assert spec.data_lineage
        if spec.data_status == "aus_daten":
            assert spec.source_version
        if spec.plausible_min is not None and spec.plausible_max is not None:
            assert spec.plausible_min <= spec.default <= spec.plausible_max


def test_initial_data_backed_parameters_are_labeled_without_claiming_import_complete():
    data_backed = [spec for spec in PARAMETER_REGISTRY.values() if spec.data_status == "aus_daten"]
    assert {spec.key for spec in data_backed} >= {
        "bevoelkerung_mio",
        "geburtenrate",
        "netto_zuwanderung",
        "aerzte_gesamt",
    }
    assert all("automated snapshot pending" in spec.source_version for spec in data_backed)


def test_medical_study_places_documents_delay_caveat():
    spec = PARAMETER_REGISTRY["medizinstudienplaetze"]
    combined = f"{spec.model_role} {spec.caveat}".lower()
    assert "6" in combined
    assert "11" in combined or "13" in combined
    assert "instantly" in combined or "instant" in combined


def test_registry_helpers_are_serializable():
    assert isinstance(list_sources()[0], dict)
    assert isinstance(list_parameters()[0], dict)
    assert evidence_summary()
    assert sources_for_parameter("population")

from pathlib import Path

from app.frameworks.pack_schema import load_pack

PACK_PATH = Path(__file__).parents[3] / "framework-packs" / "soc2"


def test_soc2_pack_contains_61_unique_requirements() -> None:
    pack = load_pack(PACK_PATH)
    identifiers = [item.external_id for item in pack.requirements]

    assert len(identifiers) == 61
    assert len(set(identifiers)) == 61
    assert {"CC6.1", "A1.1", "PI1.1", "C1.1", "P8.1"} <= set(identifiers)
    assert pack.framework.version == "2017-tsc-pof-2022"


def test_soc2_pack_separates_outcome_summaries_from_examples() -> None:
    pack = load_pack(PACK_PATH)

    assert all(item.summary.strip() for item in pack.requirements)
    assert all(item.guidance.strip() for item in pack.requirements)
    assert all(item.summary != item.guidance for item in pack.requirements)
    assert "independent" in pack.framework.disclaimer.lower()

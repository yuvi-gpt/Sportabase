from pathlib import Path

import pytest

from app.db.connection import connect_database
from app.db.migrations import initialize_database
from app.db.schema import SCHEMA
from app.knowledge.entity_bootstrap import (
    ENTITY_BOOTSTRAP_VERSION,
    bootstrap_verified_entities,
)
from app.knowledge.entities import resolve_entity_alias


@pytest.fixture
def entity_db(tmp_path: Path):
    db_path = tmp_path / "entity-bootstrap.db"

    def factory():
        return connect_database(db_path)

    initialize_database(factory, SCHEMA)
    return factory


def _count(factory, table: str) -> int:
    conn = factory()
    try:
        return int(
            conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
        )
    finally:
        conn.close()


def test_verified_bootstrap_creates_small_cross_sport_catalog(entity_db):
    result = bootstrap_verified_entities(
        connection_factory=entity_db,
    )

    assert result["version"] == ENTITY_BOOTSTRAP_VERSION
    assert result["entity_count"] == 5

    assert _count(entity_db, "canonical_entities") == 5
    assert _count(entity_db, "entity_aliases") == 12

    names = {
        entity["canonical_name"]
        for entity in result["entities"]
    }

    assert names == {
        "Manchester United",
        "Paris Saint-Germain",
        "McLaren Racing",
        "Mumbai Indians",
        "Kylian Mbapp\u00e9",
    }


def test_bootstrap_aliases_resolve_with_expected_scope(entity_db):
    bootstrap_verified_entities(
        connection_factory=entity_db,
    )

    cases = (
        ("MUFC", "club", "football", "Manchester United"),
        ("PSG", "club", "football", "Paris Saint-Germain"),
        ("McLaren F1", "team", "f1", "McLaren Racing"),
        ("Mumbai Indians", "team", "cricket", "Mumbai Indians"),
        ("Kylian Mbappe", "player", "football", "Kylian Mbapp\u00e9"),
    )

    for alias, entity_type, sport_key, expected_name in cases:
        result = resolve_entity_alias(
            alias_text=alias,
            entity_type=entity_type,
            sport_key=sport_key,
            connection_factory=entity_db,
        )

        assert result["status"] == "exact_unique"
        assert result["entity"]["canonical_name"] == expected_name


def test_ambiguous_mi_abbreviation_is_not_bootstrapped(entity_db):
    bootstrap_verified_entities(
        connection_factory=entity_db,
    )

    result = resolve_entity_alias(
        alias_text="MI",
        entity_type="team",
        sport_key="cricket",
        connection_factory=entity_db,
    )

    assert result["status"] == "no_match"
    assert result["entity"] is None


def test_bootstrap_is_idempotent(entity_db):
    first = bootstrap_verified_entities(
        connection_factory=entity_db,
    )

    entity_count = _count(
        entity_db,
        "canonical_entities",
    )
    alias_count = _count(
        entity_db,
        "entity_aliases",
    )

    second = bootstrap_verified_entities(
        connection_factory=entity_db,
    )

    assert first["entity_count"] == 5
    assert second["entity_count"] == 5

    assert _count(
        entity_db,
        "canonical_entities",
    ) == entity_count

    assert _count(
        entity_db,
        "entity_aliases",
    ) == alias_count

    assert entity_count == 5
    assert alias_count == 12


def test_bootstrap_policy_explicitly_prohibits_runtime_guessing(entity_db):
    result = bootstrap_verified_entities(
        connection_factory=entity_db,
    )

    assert result["policy"]["verified_static_catalog_only"] is True
    assert result["policy"]["runtime_entity_creation"] is False
    assert result["policy"]["fuzzy_matching"] is False
    assert result["policy"]["model_calls"] is False

from pathlib import Path

import pytest

from app.db.connection import connect_database
from app.db.migrations import initialize_database
from app.db.schema import SCHEMA
from app.knowledge.entities import (
    import_verified_entities,
    import_verified_entity,
    normalize_entity_alias,
    record_entity_alias,
    resolve_entity_alias,
    upsert_canonical_entity,
)


@pytest.fixture
def entity_db(tmp_path: Path):
    db_path = tmp_path / "entity-resolution.db"

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


def _create_entity(
    factory,
    *,
    entity_key: str,
    entity_type: str,
    canonical_name: str,
    sport_key: str = "",
    aliases=(),
):
    result = upsert_canonical_entity(
        entity_key=entity_key,
        entity_type=entity_type,
        canonical_name=canonical_name,
        sport_key=sport_key,
        connection_factory=factory,
    )

    entity_id = result["entity"]["id"]

    record_entity_alias(
        entity_id=entity_id,
        alias_text=canonical_name,
        alias_type="canonical_name",
        connection_factory=factory,
    )

    for alias_text, alias_type in aliases:
        record_entity_alias(
            entity_id=entity_id,
            alias_text=alias_text,
            alias_type=alias_type,
            connection_factory=factory,
        )

    return result["entity"]


def test_alias_normalization_is_nfkc_whitespace_and_case_insensitive():
    assert normalize_entity_alias("  Man   Utd  ") == "man utd"

    # Full-width Unicode letters normalize through NFKC.
    assert normalize_entity_alias("\uFF2D\uFF35\uFF26\uFF23") == "mufc"

    assert normalize_entity_alias("PSG") == "psg"
    assert normalize_entity_alias("psg") == "psg"


def test_known_aliases_resolve_to_same_canonical_entity(entity_db):
    entity = _create_entity(
        entity_db,
        entity_key="football|club|manchester-united",
        entity_type="club",
        canonical_name="Manchester United",
        sport_key="football",
        aliases=(
            ("Man Utd", "common_name"),
            ("Manchester Utd", "common_name"),
            ("MUFC", "abbreviation"),
        ),
    )

    for alias in (
        "Manchester United",
        "Man Utd",
        "Manchester Utd",
        "MUFC",
    ):
        result = resolve_entity_alias(
            alias_text=alias,
            entity_type="club",
            sport_key="football",
            connection_factory=entity_db,
        )

        assert result["status"] == "exact_unique"
        assert result["candidate_count"] == 1
        assert result["entity"]["id"] == entity["id"]
        assert result["entity"]["canonical_name"] == "Manchester United"


def test_unknown_alias_fails_closed_without_database_mutation(entity_db):
    _create_entity(
        entity_db,
        entity_key="football|club|manchester-united",
        entity_type="club",
        canonical_name="Manchester United",
        sport_key="football",
        aliases=(
            ("MUFC", "abbreviation"),
        ),
    )

    before_entities = _count(
        entity_db,
        "canonical_entities",
    )
    before_aliases = _count(
        entity_db,
        "entity_aliases",
    )

    result = resolve_entity_alias(
        alias_text="Definitely Not A Registered Club",
        connection_factory=entity_db,
    )

    after_entities = _count(
        entity_db,
        "canonical_entities",
    )
    after_aliases = _count(
        entity_db,
        "entity_aliases",
    )

    assert result["status"] == "no_match"
    assert result["entity"] is None
    assert result["candidate_count"] == 0
    assert result["candidates"] == []

    assert after_entities == before_entities
    assert after_aliases == before_aliases


def test_cross_type_ambiguity_fails_closed_but_type_scope_resolves(entity_db):
    club = _create_entity(
        entity_db,
        entity_key="football|club|phoenix",
        entity_type="club",
        canonical_name="Phoenix FC",
        sport_key="football",
        aliases=(
            ("Phoenix", "short_name"),
        ),
    )

    team = _create_entity(
        entity_db,
        entity_key="cricket|team|phoenix",
        entity_type="team",
        canonical_name="Phoenix Cricket",
        sport_key="cricket",
        aliases=(
            ("Phoenix", "short_name"),
        ),
    )

    ambiguous = resolve_entity_alias(
        alias_text="Phoenix",
        connection_factory=entity_db,
    )

    assert ambiguous["status"] == "ambiguous"
    assert ambiguous["entity"] is None
    assert ambiguous["candidate_count"] == 2

    club_result = resolve_entity_alias(
        alias_text="Phoenix",
        entity_type="club",
        connection_factory=entity_db,
    )

    assert club_result["status"] == "exact_unique"
    assert club_result["entity"]["id"] == club["id"]

    team_result = resolve_entity_alias(
        alias_text="Phoenix",
        entity_type="team",
        connection_factory=entity_db,
    )

    assert team_result["status"] == "exact_unique"
    assert team_result["entity"]["id"] == team["id"]


def test_same_type_alias_collision_does_not_silently_repoint(entity_db):
    first = _create_entity(
        entity_db,
        entity_key="football|club|united-alpha",
        entity_type="club",
        canonical_name="United Alpha",
        sport_key="football",
        aliases=(
            ("United", "short_name"),
        ),
    )

    second = _create_entity(
        entity_db,
        entity_key="football|club|united-beta",
        entity_type="club",
        canonical_name="United Beta",
        sport_key="football",
        aliases=(
            ("United", "short_name"),
        ),
    )

    result = resolve_entity_alias(
        alias_text="United",
        entity_type="club",
        sport_key="football",
        connection_factory=entity_db,
    )

    assert result["status"] == "ambiguous"
    assert result["entity"] is None
    assert result["candidate_count"] == 2

    candidate_ids = {
        candidate["id"]
        for candidate in result["candidates"]
    }

    assert candidate_ids == {
        first["id"],
        second["id"],
    }


def test_repeated_entity_and_alias_writes_are_idempotent(entity_db):
    kwargs = {
        "entity_key": "football|club|manchester-united",
        "entity_type": "club",
        "canonical_name": "Manchester United",
        "sport_key": "football",
        "connection_factory": entity_db,
    }

    first = upsert_canonical_entity(**kwargs)
    second = upsert_canonical_entity(**kwargs)

    assert first["entity"]["id"] == second["entity"]["id"]
    assert _count(entity_db, "canonical_entities") == 1

    alias_kwargs = {
        "entity_id": first["entity"]["id"],
        "alias_text": "MUFC",
        "alias_type": "abbreviation",
        "connection_factory": entity_db,
    }

    record_entity_alias(**alias_kwargs)
    record_entity_alias(**alias_kwargs)

    assert _count(entity_db, "entity_aliases") == 1

    resolved = resolve_entity_alias(
        alias_text="MUFC",
        entity_type="club",
        sport_key="football",
        connection_factory=entity_db,
    )

    assert resolved["status"] == "exact_unique"
    assert resolved["entity"]["id"] == first["entity"]["id"]


def test_explicit_accentless_alias_resolves_without_global_accent_stripping(
    entity_db,
):
    entity = _create_entity(
        entity_db,
        entity_key="football|player|kylian-mbappe",
        entity_type="player",
        canonical_name="Kylian Mbapp\u00e9",
        sport_key="football",
        aliases=(
            ("Kylian Mbappe", "common_name"),
        ),
    )

    accented = resolve_entity_alias(
        alias_text="Kylian Mbapp\u00e9",
        entity_type="player",
        sport_key="football",
        connection_factory=entity_db,
    )

    accentless = resolve_entity_alias(
        alias_text="Kylian Mbappe",
        entity_type="player",
        sport_key="football",
        connection_factory=entity_db,
    )

    assert accented["status"] == "exact_unique"
    assert accentless["status"] == "exact_unique"

    assert accented["entity"]["id"] == entity["id"]
    assert accentless["entity"]["id"] == entity["id"]

    # NFKC does not globally erase accents.
    assert (
        normalize_entity_alias("Kylian Mbapp\u00e9")
        != normalize_entity_alias("Kylian Mbappe")
    )


def test_resolver_policy_explicitly_remains_conservative(entity_db):
    result = resolve_entity_alias(
        alias_text="Unknown",
        connection_factory=entity_db,
    )

    assert result["policy"]["exact_alias_only"] is True
    assert result["policy"]["ambiguity_fails_closed"] is True
    assert result["policy"]["no_fuzzy_guessing"] is True
    assert result["policy"]["trusted_for_authority"] is False
    assert (
        result["policy"]["verified_binding_required_for_authority"]
        is True
    )

def test_verified_import_records_canonical_name_and_explicit_aliases(
    entity_db,
):
    result = import_verified_entity(
        entity_key="football|club|manchester-united",
        entity_type="club",
        canonical_name="Manchester United",
        sport_key="football",
        aliases=(
            ("Man Utd", "common_name"),
            ("Manchester Utd", "common_name"),
            ("MUFC", "abbreviation"),
        ),
        connection_factory=entity_db,
    )

    assert result["entity_created"] is True
    assert result["alias_count"] == 4

    assert _count(
        entity_db,
        "canonical_entities",
    ) == 1

    assert _count(
        entity_db,
        "entity_aliases",
    ) == 4

    for alias in (
        "Manchester United",
        "Man Utd",
        "Manchester Utd",
        "MUFC",
    ):
        resolved = resolve_entity_alias(
            alias_text=alias,
            entity_type="club",
            sport_key="football",
            connection_factory=entity_db,
        )

        assert resolved["status"] == "exact_unique"
        assert (
            resolved["entity"]["id"]
            == result["entity"]["id"]
        )


def test_verified_bulk_import_is_idempotent(
    entity_db,
):
    catalog = (
        {
            "entity_key": "football|club|paris-saint-germain",
            "entity_type": "club",
            "canonical_name": "Paris Saint-Germain",
            "sport_key": "football",
            "aliases": (
                ("PSG", "abbreviation"),
                ("Paris SG", "short_name"),
            ),
        },
        {
            "entity_key": "football|player|kylian-mbappe",
            "entity_type": "player",
            "canonical_name": "Kylian Mbapp\u00e9",
            "sport_key": "football",
            "aliases": (
                ("Kylian Mbappe", "common_name"),
            ),
        },
    )

    first = import_verified_entities(
        entities=catalog,
        connection_factory=entity_db,
    )

    second = import_verified_entities(
        entities=catalog,
        connection_factory=entity_db,
    )

    assert first["entity_count"] == 2
    assert second["entity_count"] == 2

    assert _count(
        entity_db,
        "canonical_entities",
    ) == 2

    assert _count(
        entity_db,
        "entity_aliases",
    ) == 5

import sqlite3
import sys
import tempfile
import unittest

from pathlib import Path


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(
    BACKEND_DIR
) not in sys.path:
    sys.path.insert(
        0,
        str(
            BACKEND_DIR
        ),
    )


from app.db.connection import (
    connect_database,
)

from app.db.schema import (
    SCHEMA,
)

from app.intelligence.entities import (
    CANONICAL_ENTITY_VERSION,
    ENTITY_ALIAS_VERSION,
    ENTITY_RESOLUTION_VERSION,
    canonical_entity_id_for_key,
    entity_alias_id_for_record,
    normalize_entity_alias,
    record_entity_alias,
    resolve_entity_alias,
    upsert_canonical_entity,
)


class CanonicalEntityPersistenceTests(
    unittest.TestCase
):
    def setUp(
        self,
    ):
        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        self.db_path = (
            Path(
                self.temp_dir.name
            )
            / "entities.db"
        )

        conn = connect_database(
            self.db_path
        )

        try:
            conn.executescript(
                SCHEMA
            )

            conn.commit()

        finally:
            conn.close()

    def tearDown(
        self,
    ):
        self.temp_dir.cleanup()

    def connection_factory(
        self,
    ):
        return connect_database(
            self.db_path
        )

    def entity(
        self,
        *,
        key="football|club|arsenal",
        entity_type="club",
        canonical_name="Arsenal",
        sport_key="football",
    ):
        return (
            upsert_canonical_entity(
                entity_key=key,
                entity_type=(
                    entity_type
                ),
                canonical_name=(
                    canonical_name
                ),
                sport_key=(
                    sport_key
                ),
                seen_at=(
                    "2026-08-15T16:30:00Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

    def alias(
        self,
        entity,
        *,
        text="Arsenal FC",
        alias_type="common_name",
    ):
        return (
            record_entity_alias(
                entity_id=(
                    entity[
                        "entity"
                    ][
                        "id"
                    ]
                ),
                alias_text=text,
                alias_type=(
                    alias_type
                ),
                seen_at=(
                    "2026-08-15T16:31:00Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

    def count(
        self,
        table,
    ):
        conn = self.connection_factory()

        try:
            return int(
                conn.execute(
                    (
                        "SELECT COUNT(*) "
                        f"FROM {table}"
                    )
                ).fetchone()[0]
            )

        finally:
            conn.close()

    def test_entity_upsert_is_deterministic_and_idempotent(
        self,
    ):
        first = self.entity()

        second = self.entity(
            canonical_name=(
                "Arsenal Football Club"
            )
        )

        expected_id = (
            canonical_entity_id_for_key(
                "football|club|arsenal"
            )
        )

        self.assertEqual(
            first[
                "version"
            ],
            CANONICAL_ENTITY_VERSION,
        )

        self.assertEqual(
            first[
                "entity"
            ][
                "id"
            ],
            expected_id,
        )

        self.assertEqual(
            second[
                "entity"
            ][
                "id"
            ],
            expected_id,
        )

        self.assertEqual(
            second[
                "entity"
            ][
                "canonical_name"
            ],
            "Arsenal Football Club",
        )

        self.assertEqual(
            self.count(
                "canonical_entities"
            ),
            1,
        )

        self.assertTrue(
            second[
                "policy"
            ][
                "entity_record_alone_does_not_establish_authority"
            ]
        )

    def test_entity_type_or_sport_scope_cannot_mutate_existing_key(
        self,
    ):
        self.entity()

        with self.assertRaises(
            ValueError
        ):
            self.entity(
                entity_type="team",
            )

        with self.assertRaises(
            ValueError
        ):
            self.entity(
                sport_key="basketball",
            )

        self.assertEqual(
            self.count(
                "canonical_entities"
            ),
            1,
        )

    def test_alias_normalization_and_identity_are_deterministic(
        self,
    ):
        entity = self.entity()

        first = self.alias(
            entity,
            text="Arsenal-FC",
        )

        second = self.alias(
            entity,
            text="  arsenal fc  ",
        )

        self.assertEqual(
            normalize_entity_alias(
                "Arsenal-FC"
            ),
            "arsenal fc",
        )

        self.assertEqual(
            first[
                "version"
            ],
            ENTITY_ALIAS_VERSION,
        )

        self.assertEqual(
            first[
                "alias"
            ][
                "id"
            ],
            second[
                "alias"
            ][
                "id"
            ],
        )

        self.assertEqual(
            first[
                "alias"
            ][
                "id"
            ],
            entity_alias_id_for_record(
                entity_id=(
                    entity[
                        "entity"
                    ][
                        "id"
                    ]
                ),
                alias_text=(
                    "ARSENAL FC"
                ),
                alias_type=(
                    "common_name"
                ),
            ),
        )

        self.assertEqual(
            self.count(
                "entity_aliases"
            ),
            1,
        )

    def test_unique_alias_resolves_candidate_but_never_authority(
        self,
    ):
        entity = self.entity()

        self.alias(
            entity
        )

        result = (
            resolve_entity_alias(
                alias_text=(
                    "ARSENAL-FC"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.assertEqual(
            result[
                "version"
            ],
            ENTITY_RESOLUTION_VERSION,
        )

        self.assertEqual(
            result[
                "status"
            ],
            "exact_unique",
        )

        self.assertEqual(
            result[
                "candidate_count"
            ],
            1,
        )

        self.assertEqual(
            result[
                "entity"
            ][
                "id"
            ],
            entity[
                "entity"
            ][
                "id"
            ],
        )

        self.assertFalse(
            result[
                "policy"
            ][
                "trusted_for_authority"
            ]
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "verified_binding_required_for_authority"
            ]
        )

    def test_ambiguous_alias_fails_closed(
        self,
    ):
        arsenal = self.entity()

        other = self.entity(
            key=(
                "football|club|"
                "arsenal-example"
            ),
            canonical_name=(
                "Arsenal Example"
            ),
        )

        self.alias(
            arsenal,
            text="Arsenal",
        )

        self.alias(
            other,
            text="Arsenal",
        )

        result = (
            resolve_entity_alias(
                alias_text="Arsenal",
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            "ambiguous",
        )

        self.assertIsNone(
            result[
                "entity"
            ]
        )

        self.assertEqual(
            result[
                "candidate_count"
            ],
            2,
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "ambiguity_fails_closed"
            ]
        )

    def test_scope_filter_can_disambiguate_without_becoming_trusted(
        self,
    ):
        club = self.entity(
            key=(
                "football|club|united"
            ),
            entity_type="club",
            canonical_name="United",
            sport_key="football",
        )

        team = self.entity(
            key=(
                "basketball|team|united"
            ),
            entity_type="team",
            canonical_name="United",
            sport_key="basketball",
        )

        self.alias(
            club,
            text="United",
        )

        self.alias(
            team,
            text="United",
        )

        broad = (
            resolve_entity_alias(
                alias_text="United",
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        narrowed = (
            resolve_entity_alias(
                alias_text="United",
                entity_type="club",
                sport_key="football",
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.assertEqual(
            broad[
                "status"
            ],
            "ambiguous",
        )

        self.assertEqual(
            narrowed[
                "status"
            ],
            "exact_unique",
        )

        self.assertEqual(
            narrowed[
                "entity"
            ][
                "id"
            ],
            club[
                "entity"
            ][
                "id"
            ],
        )

        self.assertFalse(
            narrowed[
                "policy"
            ][
                "trusted_for_authority"
            ]
        )

    def test_no_match_returns_no_match_without_guessing(
        self,
    ):
        self.entity()

        result = (
            resolve_entity_alias(
                alias_text=(
                    "Completely Unknown Club"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            "no_match",
        )

        self.assertEqual(
            result[
                "candidate_count"
            ],
            0,
        )

        self.assertIsNone(
            result[
                "entity"
            ]
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "no_fuzzy_guessing"
            ]
        )

    def test_unsupported_types_fail_before_persistence(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            self.entity(
                entity_type=(
                    "random_thing"
                ),
            )

        self.assertEqual(
            self.count(
                "canonical_entities"
            ),
            0,
        )

        entity = self.entity()

        with self.assertRaises(
            ValueError
        ):
            self.alias(
                entity,
                alias_type=(
                    "domain"
                ),
            )

        self.assertEqual(
            self.count(
                "entity_aliases"
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()
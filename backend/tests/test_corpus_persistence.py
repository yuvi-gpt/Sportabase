import json
import sqlite3
import sys
import tempfile
import unittest

from pathlib import Path


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app.db.schema import SCHEMA
from app.intelligence.corpus import (
    CORPUS_RECORD_LINK_VERSION,
    CORPUS_RECORD_VERSION,
    list_corpus_record_revisions,
    record_corpus_record,
    record_corpus_record_link,
)


class CorpusPersistenceTests(
    unittest.TestCase
):
    def setUp(
        self,
    ):
        self.tempdir = (
            tempfile.TemporaryDirectory()
        )

        self.db_path = Path(
            self.tempdir.name
        ) / "corpus.sqlite"

        self.time = (
            "2026-08-14T06:30:00+00:00"
        )

        conn = self.connection_factory()

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
        self.tempdir.cleanup()

    def connection_factory(
        self,
    ):
        conn = sqlite3.connect(
            self.db_path
        )

        conn.row_factory = sqlite3.Row

        conn.execute(
            "PRAGMA foreign_keys = ON"
        )

        return conn

    def record(
        self,
        *,
        origin="remote_api",
        family="structured_sports_data",
        dataset="openf1",
        external_id="record-1",
        adapter="openf1-v1",
        sport="motorsport",
        competition="formula-1",
        season="2026",
        event_type="lap",
        granularity="atomic_event",
        measurement="direct",
        payload=None,
        canonical_url="",
        normalize_url=None,
    ):
        return record_corpus_record(
            origin_type=origin,
            data_family=family,
            dataset_name=dataset,
            external_record_id=(
                external_id
            ),
            adapter_version=adapter,
            sport_key=sport,
            competition_key=(
                competition
            ),
            season_key=season,
            event_type=event_type,
            granularity=granularity,
            measurement_kind=(
                measurement
            ),
            payload=(
                payload
                if payload is not None
                else {
                    "lap_number": 12,
                    "lap_time": 81.42,
                }
            ),
            canonical_url=(
                canonical_url
            ),
            occurred_at=self.time,
            ingested_at=self.time,
            normalize_url=(
                normalize_url
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

    def insert_targets(
        self,
    ):
        conn = self.connection_factory()

        try:
            conn.execute(
                """
                INSERT INTO intelligence_stories (
                  id,
                  canonical_key,
                  canonical_title,
                  status,
                  first_seen_at,
                  last_seen_at,
                  metadata_json
                )
                VALUES (
                  ?, ?, ?, ?, ?, ?, '{}'
                )
                """,
                (
                    "story-1",
                    "story-key-1",
                    "Story One",
                    "developing",
                    self.time,
                    self.time,
                ),
            )

            conn.execute(
                """
                INSERT INTO media_items (
                  id,
                  canonical_url,
                  mode,
                  title,
                  latest_content_hash,
                  first_seen_at,
                  last_seen_at,
                  metadata_json
                )
                VALUES (
                  ?, ?, ?, ?, ?, ?, ?, '{}'
                )
                """,
                (
                    "media-1",
                    "https://example.com/story",
                    "article",
                    "Story One",
                    "hash-1",
                    self.time,
                    self.time,
                ),
            )

            conn.execute(
                """
                INSERT INTO intelligence_claims (
                  id,
                  canonical_key,
                  subject_key,
                  canonical_text,
                  claim_type,
                  first_seen_at,
                  last_seen_at,
                  metadata_json
                )
                VALUES (
                  ?, ?, ?, ?, ?, ?, ?, '{}'
                )
                """,
                (
                    "claim-1",
                    "claim-key-1",
                    "subject-1",
                    "Example claim",
                    "assertion",
                    self.time,
                    self.time,
                ),
            )

            conn.commit()

        finally:
            conn.close()

    def test_schema_has_multi_sport_corpus_fields(
        self,
    ):
        conn = self.connection_factory()

        try:
            columns = {
                row["name"]
                for row in conn.execute(
                    """
                    PRAGMA table_info(
                      corpus_records
                    )
                    """
                ).fetchall()
            }

            tables = {
                row["name"]
                for row in conn.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    """
                ).fetchall()
            }

        finally:
            conn.close()

        self.assertIn(
            "corpus_records",
            tables,
        )

        self.assertIn(
            "corpus_record_links",
            tables,
        )

        for field in (
            "data_family",
            "sport_key",
            "competition_key",
            "season_key",
            "event_type",
            "granularity",
            "measurement_kind",
            "occurred_at",
            "payload_json",
        ):
            self.assertIn(
                field,
                columns,
            )

    def test_exact_reimport_is_idempotent(
        self,
    ):
        first = self.record()

        second = record_corpus_record(
            origin_type="remote_api",
            data_family=(
                "structured_sports_data"
            ),
            dataset_name="openf1",
            external_record_id="record-1",
            adapter_version="openf1-v1",
            sport_key="motorsport",
            competition_key="formula-1",
            season_key="2026",
            event_type="lap",
            granularity="atomic_event",
            measurement_kind="direct",
            payload={
                "lap_time": 81.42,
                "lap_number": 12,
            },
            occurred_at=self.time,
            ingested_at=(
                "2027-01-01T00:00:00+00:00"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        self.assertTrue(
            first["created"]
        )

        self.assertFalse(
            second["created"]
        )

        self.assertEqual(
            first["record"]["id"],
            second["record"]["id"],
        )

        self.assertEqual(
            second[
                "record"
            ][
                "ingested_at"
            ],
            self.time,
        )

    def test_changed_payload_creates_append_only_revision(
        self,
    ):
        first = self.record(
            payload={
                "lap": 12,
                "speed": 300,
            }
        )

        second = self.record(
            payload={
                "lap": 12,
                "speed": 301,
            }
        )

        revisions = (
            list_corpus_record_revisions(
                origin_type="remote_api",
                dataset_name="openf1",
                external_record_id=(
                    "record-1"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.assertNotEqual(
            first["record"]["id"],
            second["record"]["id"],
        )

        self.assertEqual(
            len(revisions),
            2,
        )

    def test_adapter_version_creates_revision(
        self,
    ):
        first = self.record(
            adapter="openf1-v1"
        )

        second = self.record(
            adapter="openf1-v2"
        )

        self.assertNotEqual(
            first["record"]["id"],
            second["record"]["id"],
        )

    def test_dimension_change_creates_revision(
        self,
    ):
        first = self.record(
            event_type="lap"
        )

        second = self.record(
            event_type="mini-sector"
        )

        self.assertNotEqual(
            first["record"]["id"],
            second["record"]["id"],
        )

    def test_dataset_namespace_prevents_collision(
        self,
    ):
        first = self.record(
            dataset="openf1",
            external_id="42",
        )

        second = self.record(
            dataset="fastf1",
            external_id="42",
        )

        self.assertNotEqual(
            first["record"]["id"],
            second["record"]["id"],
        )

    def test_arbitrary_future_sport_key_is_supported(
        self,
    ):
        result = self.record(
            dataset="future-provider",
            sport="padel",
            competition="world-tour",
            event_type="point",
        )

        self.assertEqual(
            result[
                "record"
            ][
                "sport_key"
            ],
            "padel",
        )

    def test_macro_aggregate_payload_is_preserved(
        self,
    ):
        result = self.record(
            dataset="cricket-example",
            sport="cricket",
            competition="ipl",
            event_type="team-performance",
            granularity="aggregate",
            measurement="derived",
            payload={
                "score": 188,
                "wickets": 6,
                "nrr": 0.742,
            },
        )

        payload = json.loads(
            result[
                "record"
            ][
                "payload_json"
            ]
        )

        self.assertEqual(
            payload["score"],
            188,
        )

        self.assertEqual(
            payload["nrr"],
            0.742,
        )

    def test_micro_atomic_payload_is_preserved(
        self,
    ):
        result = self.record(
            dataset="football-events",
            sport="football",
            competition="premier-league",
            event_type="shot",
            granularity="atomic_event",
            measurement="modelled",
            payload={
                "x": 88.2,
                "y": 34.1,
                "xg": 0.163,
                "xga_context": 0.163,
                "under_pressure": True,
                "sequence_id": "seq-19",
            },
        )

        payload = json.loads(
            result[
                "record"
            ][
                "payload_json"
            ]
        )

        self.assertEqual(
            payload["sequence_id"],
            "seq-19",
        )

        self.assertTrue(
            payload[
                "under_pressure"
            ]
        )

    def test_structured_sports_data_requires_sport(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "requires a sport key",
        ):
            self.record(
                sport=""
            )

    def test_invalid_data_family_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "data family",
        ):
            self.record(
                family="whatever"
            )

    def test_invalid_measurement_kind_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "measurement kind",
        ):
            self.record(
                measurement="magic"
            )

    def test_url_normalization_is_preserved(
        self,
    ):
        result = self.record(
            canonical_url=(
                "HTTPS://Example.COM/Event#frag"
            ),
            normalize_url=(
                lambda value: (
                    value.lower().split(
                        "#",
                        1,
                    )[0]
                )
            ),
        )

        self.assertEqual(
            result[
                "record"
            ][
                "canonical_url"
            ],
            "https://example.com/event",
        )

    def test_record_links_to_existing_graph_idempotently(
        self,
    ):
        self.insert_targets()

        record = self.record()

        record_id = (
            record["record"]["id"]
        )

        first = record_corpus_record_link(
            corpus_record_id=record_id,
            story_id="story-1",
            linked_at=self.time,
            connection_factory=(
                self.connection_factory
            ),
        )

        second = record_corpus_record_link(
            corpus_record_id=record_id,
            story_id="story-1",
            linked_at=(
                "2027-01-01T00:00:00+00:00"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        self.assertEqual(
            first["version"],
            CORPUS_RECORD_LINK_VERSION,
        )

        self.assertTrue(
            first["created"]
        )

        self.assertFalse(
            second["created"]
        )

    def test_record_can_link_to_story_media_and_claim(
        self,
    ):
        self.insert_targets()

        record_id = (
            self.record()[
                "record"
            ][
                "id"
            ]
        )

        links = [
            record_corpus_record_link(
                corpus_record_id=record_id,
                story_id="story-1",
                connection_factory=(
                    self.connection_factory
                ),
            ),
            record_corpus_record_link(
                corpus_record_id=record_id,
                media_item_id="media-1",
                connection_factory=(
                    self.connection_factory
                ),
            ),
            record_corpus_record_link(
                corpus_record_id=record_id,
                claim_id="claim-1",
                connection_factory=(
                    self.connection_factory
                ),
            ),
        ]

        self.assertEqual(
            len(
                {
                    result[
                        "link"
                    ][
                        "id"
                    ]
                    for result in links
                }
            ),
            3,
        )

    def test_link_requires_exactly_one_target(
        self,
    ):
        record_id = (
            self.record()[
                "record"
            ][
                "id"
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "exactly one target",
        ):
            record_corpus_record_link(
                corpus_record_id=record_id,
                connection_factory=(
                    self.connection_factory
                ),
            )

        self.insert_targets()

        with self.assertRaisesRegex(
            ValueError,
            "exactly one target",
        ):
            record_corpus_record_link(
                corpus_record_id=record_id,
                story_id="story-1",
                claim_id="claim-1",
                connection_factory=(
                    self.connection_factory
                ),
            )


if __name__ == "__main__":
    unittest.main()

import io
import json
import sys
import unittest
import zipfile

from pathlib import Path


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app.services.corpus_adapters import (
    REMOTE_CORPUS_ADAPTER_VERSION,
    build_cricsheet_request,
    build_openf1_request,
    build_statsbomb_open_request,
    fetch_remote_request,
    ingest_normalized_records,
    normalize_cricsheet_matches,
    normalize_openf1_rows,
    normalize_statsbomb_rows,
    read_cricsheet_json_archive,
)


class FakeResponse:
    def __init__(
        self,
        *,
        status_code=200,
        payload=None,
        content=b"",
    ):
        self.status_code = (
            status_code
        )

        self._payload = payload
        self.content = content

    def json(
        self,
    ):
        return self._payload


class CorpusRemoteAdapterTests(
    unittest.TestCase
):
    def test_openf1_request_is_deterministic(
        self,
    ):
        request = build_openf1_request(
            endpoint="laps",
            filters={
                "session_key": 123,
                "driver_number": 44,
            },
        )

        self.assertEqual(
            request[
                "provider_key"
            ],
            "openf1",
        )

        self.assertEqual(
            request[
                "expected_format"
            ],
            "json",
        )

        self.assertTrue(
            request[
                "url"
            ].endswith(
                (
                    "/laps?"
                    "driver_number=44"
                    "&session_key=123"
                )
            )
        )

    def test_openf1_unknown_endpoint_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "Unsupported OpenF1",
        ):
            build_openf1_request(
                endpoint="magic"
            )

    def test_openf1_atomic_row_normalization(
        self,
    ):
        rows = normalize_openf1_rows(
            endpoint="laps",
            season_key="2026",
            rows=[
                {
                    "session_key": 10,
                    "driver_number": 44,
                    "lap_number": 20,
                    "lap_duration": 81.1,
                    "date_start": (
                        "2026-05-01T12:00:00Z"
                    ),
                }
            ],
        )

        row = rows[0]

        self.assertEqual(
            row["sport_key"],
            "motorsport",
        )

        self.assertEqual(
            row[
                "competition_key"
            ],
            "formula-1",
        )

        self.assertEqual(
            row["event_type"],
            "lap",
        )

        self.assertEqual(
            row["granularity"],
            "atomic_event",
        )

        self.assertEqual(
            row[
                "external_record_id"
            ],
            "laps|10|44|20",
        )

    def test_openf1_meeting_is_macro_record(
        self,
    ):
        row = normalize_openf1_rows(
            endpoint="meetings",
            rows=[
                {
                    "meeting_key": 99,
                    "year": 2026,
                    "meeting_name": (
                        "Example GP"
                    ),
                }
            ],
        )[0]

        self.assertEqual(
            row["event_type"],
            "meeting",
        )

        self.assertEqual(
            row["granularity"],
            "record",
        )

        self.assertEqual(
            row["season_key"],
            "2026",
        )

    def test_statsbomb_competitions_request(
        self,
    ):
        request = (
            build_statsbomb_open_request(
                resource="competitions"
            )
        )

        self.assertTrue(
            request["url"].endswith(
                "/competitions.json"
            )
        )

    def test_statsbomb_match_request_requires_scope(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "competition and season",
        ):
            build_statsbomb_open_request(
                resource="matches"
            )

    def test_statsbomb_event_request_and_normalization(
        self,
    ):
        request = (
            build_statsbomb_open_request(
                resource="events",
                match_id=1234,
            )
        )

        self.assertTrue(
            request["url"].endswith(
                "/events/1234.json"
            )
        )

        row = normalize_statsbomb_rows(
            resource="events",
            match_id=1234,
            competition_key=(
                "premier-league"
            ),
            season_key="2025-26",
            rows=[
                {
                    "id": "event-uuid",
                    "type": {
                        "name": "Shot",
                    },
                    "location": [
                        101.0,
                        38.0,
                    ],
                    "shot": {
                        "statsbomb_xg": (
                            0.21
                        ),
                    },
                }
            ],
        )[0]

        self.assertEqual(
            row["sport_key"],
            "football",
        )

        self.assertEqual(
            row["event_type"],
            "shot",
        )

        self.assertEqual(
            row["granularity"],
            "atomic_event",
        )

        self.assertEqual(
            row[
                "payload"
            ][
                "shot"
            ][
                "statsbomb_xg"
            ],
            0.21,
        )

    def test_cricsheet_request_accepts_ipl_archive(
        self,
    ):
        request = build_cricsheet_request(
            archive_name=(
                "ipl_json.zip"
            )
        )

        self.assertEqual(
            request[
                "provider_key"
            ],
            "cricsheet",
        )

        self.assertTrue(
            request[
                "url"
            ].endswith(
                "/ipl_json.zip"
            )
        )

    def test_cricsheet_request_rejects_unsafe_path(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "safe",
        ):
            build_cricsheet_request(
                archive_name=(
                    "../ipl_json.zip"
                )
            )

    def test_cricsheet_zip_parser_preserves_match_id(
        self,
    ):
        buffer = io.BytesIO()

        with zipfile.ZipFile(
            buffer,
            "w",
        ) as archive:
            archive.writestr(
                "12345.json",
                json.dumps(
                    {
                        "info": {
                            "season": 2026,
                            "dates": [
                                "2026-04-01",
                            ],
                        },
                        "innings": [
                            {
                                "team": "A",
                            }
                        ],
                    }
                ),
            )

        rows = (
            read_cricsheet_json_archive(
                buffer.getvalue()
            )
        )

        self.assertEqual(
            rows[0][
                "external_record_id"
            ],
            "12345",
        )

    def test_cricsheet_match_normalization_preserves_delivery_data(
        self,
    ):
        row = (
            normalize_cricsheet_matches(
                competition_key="ipl",
                matches=[
                    {
                        "external_record_id": (
                            "12345"
                        ),
                        "payload": {
                            "info": {
                                "season": 2026,
                                "dates": [
                                    "2026-04-01",
                                ],
                            },
                            "innings": [
                                {
                                    "team": (
                                        "A"
                                    ),
                                    "overs": [],
                                }
                            ],
                        },
                    }
                ],
            )[0]
        )

        self.assertEqual(
            row["sport_key"],
            "cricket",
        )

        self.assertEqual(
            row[
                "competition_key"
            ],
            "ipl",
        )

        self.assertEqual(
            row["season_key"],
            "2026",
        )

        self.assertTrue(
            row[
                "metadata"
            ][
                "contains_delivery_data"
            ]
        )

    def test_remote_json_fetch_uses_injected_client(
        self,
    ):
        calls = []

        def fake_get(
            url,
            *,
            timeout,
        ):
            calls.append(
                (
                    url,
                    timeout,
                )
            )

            return FakeResponse(
                payload=[
                    {
                        "a": 1,
                    }
                ]
            )

        request = build_openf1_request(
            endpoint="meetings",
            filters={
                "year": 2026,
            },
        )

        payload = fetch_remote_request(
            request,
            http_get=fake_get,
            timeout_seconds=7,
        )

        self.assertEqual(
            payload,
            [
                {
                    "a": 1,
                }
            ],
        )

        self.assertEqual(
            calls[0][1],
            7,
        )

    def test_remote_zip_fetch_uses_injected_client(
        self,
    ):
        request = build_cricsheet_request(
            archive_name=(
                "ipl_json.zip"
            )
        )

        payload = fetch_remote_request(
            request,
            http_get=(
                lambda url, timeout: (
                    FakeResponse(
                        content=b"zip-bytes"
                    )
                )
            ),
        )

        self.assertEqual(
            payload,
            b"zip-bytes",
        )

    def test_remote_http_failure_is_not_silenced(
        self,
    ):
        request = build_openf1_request(
            endpoint="meetings"
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "HTTP 503",
        ):
            fetch_remote_request(
                request,
                http_get=(
                    lambda url, timeout: (
                        FakeResponse(
                            status_code=503
                        )
                    )
                ),
            )

    def test_ingest_normalized_records_is_idempotency_aware(
        self,
    ):
        calls = []

        def recorder(
            **kwargs,
        ):
            calls.append(
                kwargs
            )

            return {
                "created": (
                    len(
                        calls
                    )
                    == 1
                )
            }

        records = [
            {
                "dataset_name": "a",
            },
            {
                "dataset_name": "b",
            },
        ]

        result = ingest_normalized_records(
            records=records,
            connection_factory=(
                "fake-connection"
            ),
            recorder=recorder,
        )

        self.assertEqual(
            result[
                "version"
            ],
            REMOTE_CORPUS_ADAPTER_VERSION,
        )

        self.assertEqual(
            result[
                "counts"
            ][
                "processed"
            ],
            2,
        )

        self.assertEqual(
            result[
                "counts"
            ][
                "created"
            ],
            1,
        )

        self.assertEqual(
            result[
                "counts"
            ][
                "existing"
            ],
            1,
        )

        self.assertFalse(
            result[
                "live_merit_effect_enabled"
            ]
        )


if __name__ == "__main__":
    unittest.main()

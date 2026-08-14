import inspect
import sys
import unittest

from pathlib import Path
from unittest.mock import (
    Mock,
    patch,
)


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app import main

from app.services import (
    intelligence_facade,
)


class IntelligenceFacadeModuleTests(
    unittest.TestCase
):
    def test_service_has_no_main_or_route_coupling(
        self,
    ):
        source = Path(
            intelligence_facade.__file__
        ).read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            "from app.main",
            source,
        )

        self.assertNotIn(
            "from app import main",
            source,
        )

        self.assertNotIn(
            "@app.",
            source,
        )

    def test_source_domain_uses_current_main_dependencies(
        self,
    ):
        normalizer = Mock(
            return_value=(
                "https://example.com/story"
            )
        )

        with (
            patch.object(
                main,
                "normalized_analysis_url",
                normalizer,
            ),
            patch.object(
                main,
                "_source_domain_for_url_impl",
                return_value="example.com",
            ) as implementation,
        ):
            result = (
                main.source_domain_for_url(
                    "https://example.com/story"
                )
            )

        self.assertEqual(
            result,
            "example.com",
        )

        implementation.assert_called_once_with(
            "https://example.com/story",
            normalize_url=normalizer,
        )

    def test_source_upsert_uses_current_db_and_domain_resolver(
        self,
    ):
        sentinel = {
            "id": "source-1"
        }

        connection_factory = Mock()
        domain_resolver = Mock()

        with (
            patch.object(
                main,
                "db_conn",
                connection_factory,
            ),
            patch.object(
                main,
                "source_domain_for_url",
                domain_resolver,
            ),
            patch.object(
                main,
                "_upsert_intelligence_source_impl",
                return_value=sentinel,
            ) as implementation,
        ):
            result = (
                main.upsert_intelligence_source(
                    url=(
                        "https://example.com/story"
                    )
                )
            )

        self.assertIs(
            result,
            sentinel,
        )

        kwargs = (
            implementation
            .call_args
            .kwargs
        )

        self.assertIs(
            kwargs[
                "connection_factory"
            ],
            connection_factory,
        )

        self.assertIs(
            kwargs[
                "domain_resolver"
            ],
            domain_resolver,
        )

    def test_record_evidence_uses_current_db_and_normalizer(
        self,
    ):
        sentinel = {
            "id": "evidence-1"
        }

        connection_factory = Mock()
        normalizer = Mock()

        with (
            patch.object(
                main,
                "db_conn",
                connection_factory,
            ),
            patch.object(
                main,
                "normalized_analysis_url",
                normalizer,
            ),
            patch.object(
                main,
                "_record_evidence_impl",
                return_value=sentinel,
            ) as implementation,
        ):
            result = main.record_evidence(
                evidence_type="article",
                subject_key="subject-1",
                observed_at=(
                    "2026-08-14T10:00:00+00:00"
                ),
            )

        self.assertIs(
            result,
            sentinel,
        )

        kwargs = (
            implementation
            .call_args
            .kwargs
        )

        self.assertIs(
            kwargs[
                "connection_factory"
            ],
            connection_factory,
        )

        self.assertIs(
            kwargs[
                "normalize_url"
            ],
            normalizer,
        )

    def test_observation_dependency_uses_current_database(
        self,
    ):
        sentinel = {
            "id": "dependency-1"
        }

        connection_factory = Mock()

        with (
            patch.object(
                main,
                "db_conn",
                connection_factory,
            ),
            patch.object(
                main,
                "_record_observation_dependency_impl",
                return_value=sentinel,
            ) as implementation,
        ):
            result = (
                main.record_observation_dependency(
                    relationship_type=(
                        "reported_from"
                    ),
                    observed_at=(
                        "2026-08-14T10:00:00+00:00"
                    ),
                    upstream_source_id=(
                        "source-1"
                    ),
                    downstream_source_observation_id=(
                        "observation-1"
                    ),
                )
            )

        self.assertIs(
            result,
            sentinel,
        )

        self.assertIs(
            implementation
            .call_args
            .kwargs[
                "connection_factory"
            ],
            connection_factory,
        )

    def test_context_loader_uses_current_database(
        self,
    ):
        sentinel = {
            "context": []
        }

        connection_factory = Mock()

        with (
            patch.object(
                main,
                "db_conn",
                connection_factory,
            ),
            patch.object(
                main,
                "_load_evidence_context_for_media_item_impl",
                return_value=sentinel,
            ) as implementation,
        ):
            result = (
                main.load_evidence_context_for_media_item(
                    media_item_id="media-1"
                )
            )

        self.assertIs(
            result,
            sentinel,
        )

        self.assertIs(
            implementation
            .call_args
            .kwargs[
                "connection_factory"
            ],
            connection_factory,
        )

    def test_analysis_state_loader_uses_current_database(
        self,
    ):
        sentinel = {
            "bundle": {}
        }

        connection_factory = Mock()

        with (
            patch.object(
                main,
                "db_conn",
                connection_factory,
            ),
            patch.object(
                main,
                "_load_evidence_analysis_state_for_media_item_impl",
                return_value=sentinel,
            ) as implementation,
        ):
            result = (
                main.load_evidence_analysis_state_for_media_item(
                    media_item_id="media-1"
                )
            )

        self.assertIs(
            result,
            sentinel,
        )

        self.assertIs(
            implementation
            .call_args
            .kwargs[
                "connection_factory"
            ],
            connection_factory,
        )

    def test_story_media_sql_moved_out_of_main(
        self,
    ):
        main_source = Path(
            main.__file__
        ).read_text(
            encoding="utf-8"
        )

        service_source = Path(
            intelligence_facade.__file__
        ).read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            "INSERT INTO story_media_links",
            main_source,
        )

        self.assertIn(
            "INSERT INTO story_media_links",
            service_source,
        )

        wrapper_source = inspect.getsource(
            main.link_media_item_to_story
        )

        self.assertIn(
            "_invoke_intelligence_facade",
            wrapper_source,
        )


if __name__ == "__main__":
    unittest.main()

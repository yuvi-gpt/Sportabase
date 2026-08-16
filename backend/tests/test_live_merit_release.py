import copy
import json
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
from app.db.schema import SCHEMA
from app.intelligence.claims import (
    claim_id_for_canonical_key,
    record_claim_link,
    upsert_intelligence_claim,
)
from app.intelligence.entities import (
    upsert_canonical_entity,
)
from app.intelligence.entity_bindings import (
    record_verified_claim_entity_participant,
    record_verified_source_entity_binding,
)
from app.intelligence.evidence import (
    record_evidence,
)
from app.intelligence.observations import (
    record_source_observation,
)
from app.intelligence.sources import (
    source_domain_for_url,
    upsert_intelligence_source,
)
from app.analysis.merit_score_release import (
    build_merit_score_release_certificate,
)
from app.services.article_rules import (
    badge,
)
from app.services.direct_stakeholder_independence_verifier import (
    persist_direct_stakeholder_independence_verification,
)
from app.services.live_merit_release import (
    LIVE_MERIT_RELEASE_REQUIRED_CERTIFICATE_SHA256,
    LIVE_MERIT_RELEASE_RUNTIME_VERSION,
    apply_certified_live_merit,
    live_merit_release_cache_token,
)


CERTIFICATE_PATH = (
    BACKEND_DIR
    / "data"
    / "merit_score_release_certificate.json"
)


class LiveMeritReleaseTests(
    unittest.TestCase
):
    def setUp(
        self,
    ):
        self.temp = (
            tempfile.TemporaryDirectory()
        )
        self.db_path = (
            Path(
                self.temp.name
            )
            / "live-merit.db"
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
        self.temp.cleanup()

    def connection_factory(
        self,
    ):
        return connect_database(
            self.db_path
        )

    @staticmethod
    def normalize_url(
        value,
    ):
        return str(
            value or ""
        ).strip().lower()

    def domain_resolver(
        self,
        value,
    ):
        return source_domain_for_url(
            value,
            normalize_url=(
                self.normalize_url
            ),
        )

    @staticmethod
    def legacy_score(
        total=60,
    ):
        return {
            "total": total,
            "badge": badge(
                total
            ),
            "reasons": [
                "Legacy reason."
            ],
            "components": {
                "corroboration": 4.0,
                "source_score": 15.0,
            },
            "calculation": {
                "raw_total": float(
                    total
                ),
                "penalty": 0.0,
                "before_soft_ceilings": (
                    float(
                        total
                    )
                ),
                "final_total": total,
            },
        }

    @staticmethod
    def bundle_link(
        row,
    ):
        return {
            "id": row[
                "id"
            ],
            "claim_id": row[
                "claim_id"
            ],
            "target_type": (
                "source_observation"
            ),
            "target_id": row[
                "source_observation_id"
            ],
            "relationship_type": row[
                "relationship_type"
            ],
            "confidence": row[
                "confidence"
            ],
            "observed_at": row[
                "observed_at"
            ],
        }

    def verified_evidence(
        self,
        reference_key,
        subject_key,
    ):
        return record_evidence(
            evidence_type=(
                "machine_reference"
            ),
            subject_key=(
                subject_key
            ),
            observed_at=(
                "2026-08-16T04:00:00Z"
            ),
            reference_key=(
                reference_key
            ),
            verification_status=(
                "verified"
            ),
            recorded_at=(
                "2026-08-16T04:00:01Z"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )["evidence"]

    def seed_direct_positive(
        self,
        *,
        media_item_id=(
            "media-live-1"
        ),
    ):
        claim = (
            upsert_intelligence_claim(
                canonical_key=(
                    "article-primary|"
                    + media_item_id
                    + "|kepa-transfer"
                ),
                subject_key=(
                    "transfer|kepa|"
                    "chelsea|arsenal"
                ),
                canonical_text=(
                    "Kepa moves from "
                    "Chelsea to Arsenal."
                ),
                claim_type="transfer",
                seen_at=(
                    "2026-08-16T04:00:00Z"
                ),
                id_resolver=(
                    claim_id_for_canonical_key
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        specs = [
            {
                "url": (
                    "https://www.chelseafc.com/"
                    "en/news/article/"
                    "kepa-departs-for-arsenal"
                ),
                "name": "Chelsea",
                "entity_key": (
                    "football|club|chelsea"
                ),
                "role": "origin",
            },
            {
                "url": (
                    "https://www.arsenal.com/"
                    "feature/"
                    "keeping-up-with-kepa"
                ),
                "name": "Arsenal",
                "entity_key": (
                    "football|club|arsenal"
                ),
                "role": "destination",
            },
        ]

        observations = []
        links = []

        for index, spec in enumerate(
            specs,
            start=1,
        ):
            source = (
                upsert_intelligence_source(
                    url=spec[
                        "url"
                    ],
                    display_name=(
                        spec[
                            "name"
                        ]
                    ),
                    source_type=(
                        "publisher"
                    ),
                    seen_at=(
                        "2026-08-16T04:00:00Z"
                    ),
                    domain_resolver=(
                        self.domain_resolver
                    ),
                    connection_factory=(
                        self.connection_factory
                    ),
                )
            )

            entity = (
                upsert_canonical_entity(
                    entity_key=(
                        spec[
                            "entity_key"
                        ]
                    ),
                    entity_type="club",
                    canonical_name=(
                        spec[
                            "name"
                        ]
                    ),
                    sport_key="football",
                    seen_at=(
                        "2026-08-16T04:00:00Z"
                    ),
                    connection_factory=(
                        self.connection_factory
                    ),
                )["entity"]
            )

            binding_evidence = (
                self.verified_evidence(
                    (
                        "binding-"
                        + str(
                            index
                        )
                    ),
                    (
                        "binding|"
                        + source[
                            "id"
                        ]
                        + "|"
                        + entity[
                            "id"
                        ]
                    ),
                )
            )

            record_verified_source_entity_binding(
                source_id=source[
                    "id"
                ],
                entity_id=entity[
                    "id"
                ],
                binding_type=(
                    "official_site"
                ),
                evidence_id=(
                    binding_evidence[
                        "id"
                    ]
                ),
                confidence=0.99,
                observed_at=(
                    "2026-08-16T04:00:00Z"
                ),
                recorded_at=(
                    "2026-08-16T04:00:02Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )

            participant_evidence = (
                self.verified_evidence(
                    (
                        "participant-"
                        + str(
                            index
                        )
                    ),
                    (
                        "participant|"
                        + claim[
                            "id"
                        ]
                        + "|"
                        + entity[
                            "id"
                        ]
                    ),
                )
            )

            record_verified_claim_entity_participant(
                claim_id=claim[
                    "id"
                ],
                entity_id=entity[
                    "id"
                ],
                participant_role=(
                    spec[
                        "role"
                    ]
                ),
                evidence_id=(
                    participant_evidence[
                        "id"
                    ]
                ),
                confidence=0.99,
                observed_at=(
                    "2026-08-16T04:00:00Z"
                ),
                recorded_at=(
                    "2026-08-16T04:00:03Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )

            observation = (
                record_source_observation(
                    source_id=source[
                        "id"
                    ],
                    subject_key=claim[
                        "subject_key"
                    ],
                    observation_type=(
                        "official_statement"
                    ),
                    observed_at=(
                        "2026-08-16T04:"
                        + f"{index:02d}"
                        + ":00Z"
                    ),
                    status="captured",
                    claim_summary=claim[
                        "canonical_text"
                    ],
                    provenance_url=(
                        spec[
                            "url"
                        ]
                    ),
                    confidence=0.99,
                    recorded_at=(
                        "2026-08-16T04:"
                        + f"{index:02d}"
                        + ":01Z"
                    ),
                    normalize_url=(
                        self.normalize_url
                    ),
                    connection_factory=(
                        self.connection_factory
                    ),
                )["observation"]
            )

            link = record_claim_link(
                claim_id=claim[
                    "id"
                ],
                source_observation_id=(
                    observation[
                        "id"
                    ]
                ),
                relationship_type=(
                    "supports"
                ),
                confidence=0.99,
                observed_at=(
                    observation[
                        "observed_at"
                    ]
                ),
                recorded_at=(
                    "2026-08-16T04:"
                    + f"{index:02d}"
                    + ":02Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )["link"]

            observations.append(
                observation
            )
            links.append(
                self.bundle_link(
                    link
                )
            )

        independence = (
            persist_direct_stakeholder_independence_verification(
                claim_id=claim[
                    "id"
                ],
                left_observation_id=(
                    observations[
                        0
                    ][
                        "id"
                    ]
                ),
                right_observation_id=(
                    observations[
                        1
                    ][
                        "id"
                    ]
                ),
                connection_factory=(
                    self.connection_factory
                ),
                recorded_at=(
                    "2026-08-16T04:10:00Z"
                ),
            )
        )

        self.assertTrue(
            independence[
                "persisted"
            ]
        )

        raw_assertion = (
            independence[
                "assertion"
            ][
                "assertion"
            ]
        )

        self.assertIsNotNone(
            raw_assertion[
                "observation_a_source_observation_id"
            ]
        )
        self.assertIsNotNone(
            raw_assertion[
                "observation_b_source_observation_id"
            ]
        )
        self.assertIsNone(
            raw_assertion[
                "observation_a_reporter_observation_id"
            ]
        )
        self.assertIsNone(
            raw_assertion[
                "observation_b_reporter_observation_id"
            ]
        )

        assertion = {
            "id": raw_assertion[
                "id"
            ],
            "observation_a_type": (
                "source_observation"
            ),
            "observation_a_id": (
                raw_assertion[
                    "observation_a_source_observation_id"
                ]
            ),
            "observation_b_type": (
                "source_observation"
            ),
            "observation_b_id": (
                raw_assertion[
                    "observation_b_source_observation_id"
                ]
            ),
            "provenance_evidence_id": (
                raw_assertion[
                    "provenance_evidence_id"
                ]
            ),
            "verification_status": (
                raw_assertion[
                    "verification_status"
                ]
            ),
            "confidence": raw_assertion[
                "confidence"
            ],
            "observed_at": raw_assertion[
                "observed_at"
            ],
        }

        bundle = {
            "claims": [
                claim
            ],
            "claim_links": (
                links
            ),
            "source_observations": (
                observations
            ),
            "reporter_observations": [],
            "observation_dependencies": [],
            "observation_independence_assertions": [
                assertion
            ],
        }

        return {
            "media_item_id": (
                media_item_id
            ),
            "claim": claim,
            "bundle": bundle,
            "independence": (
                independence
            ),
        }

    @staticmethod
    def synthetic_bundle(
        *,
        media_item_id,
        same_source=False,
        dependency=False,
        verified_assertion=False,
        contested=False,
    ):
        claim_id = (
            "claim-"
            + media_item_id
        )

        claim = {
            "id": claim_id,
            "canonical_key": (
                "article-primary|"
                + media_item_id
                + "|synthetic"
            ),
            "subject_key": (
                "synthetic|claim"
            ),
            "canonical_text": (
                "Synthetic claim."
            ),
            "claim_type": (
                "transfer"
            ),
        }

        first_source = (
            "source-one"
        )

        second_source = (
            first_source
            if same_source
            else "source-two"
        )

        observations = [
            {
                "id": "observation-one",
                "source_id": (
                    first_source
                ),
            },
            {
                "id": "observation-two",
                "source_id": (
                    second_source
                ),
            },
        ]

        links = [
            {
                "id": "link-one",
                "claim_id": (
                    claim_id
                ),
                "target_type": (
                    "source_observation"
                ),
                "target_id": (
                    "observation-one"
                ),
                "relationship_type": (
                    "supports"
                ),
                "confidence": 0.99,
                "observed_at": (
                    "2026-08-16T04:00:00Z"
                ),
            },
            {
                "id": "link-two",
                "claim_id": (
                    claim_id
                ),
                "target_type": (
                    "source_observation"
                ),
                "target_id": (
                    "observation-two"
                ),
                "relationship_type": (
                    "supports"
                ),
                "confidence": 0.99,
                "observed_at": (
                    "2026-08-16T04:01:00Z"
                ),
            },
        ]

        if contested:
            links.append(
                {
                    "id": (
                        "contradiction-one"
                    ),
                    "claim_id": (
                        claim_id
                    ),
                    "target_type": (
                        "source_observation"
                    ),
                    "target_id": (
                        "observation-two"
                    ),
                    "relationship_type": (
                        "contradicts"
                    ),
                    "confidence": 0.99,
                    "observed_at": (
                        "2026-08-16T04:02:00Z"
                    ),
                }
            )

        dependencies = []

        if dependency:
            dependencies.append(
                {
                    "id": (
                        "dependency-one"
                    ),
                    "downstream_type": (
                        "source_observation"
                    ),
                    "downstream_id": (
                        "observation-two"
                    ),
                    "upstream_type": (
                        "source_observation"
                    ),
                    "upstream_id": (
                        "observation-one"
                    ),
                    "relationship_type": (
                        "derived_from"
                    ),
                    "confidence": 0.99,
                    "observed_at": (
                        "2026-08-16T04:03:00Z"
                    ),
                }
            )

        assertions = []

        if verified_assertion:
            assertions.append(
                {
                    "id": (
                        "generic-model-assertion"
                    ),
                    "observation_a_type": (
                        "source_observation"
                    ),
                    "observation_a_id": (
                        "observation-one"
                    ),
                    "observation_b_type": (
                        "source_observation"
                    ),
                    "observation_b_id": (
                        "observation-two"
                    ),
                    "provenance_evidence_id": (
                        "generic-model-evidence"
                    ),
                    "verification_status": (
                        "verified"
                    ),
                    "confidence": 0.99,
                    "observed_at": (
                        "2026-08-16T04:04:00Z"
                    ),
                }
            )

        return {
            "claims": [
                claim
            ],
            "claim_links": (
                links
            ),
            "source_observations": (
                observations
            ),
            "reporter_observations": [],
            "observation_dependencies": (
                dependencies
            ),
            "observation_independence_assertions": (
                assertions
            ),
        }

    def apply(
        self,
        *,
        bundle,
        media_item_id,
        legacy_score=None,
        certificate_path=(
            CERTIFICATE_PATH
        ),
        enabled=True,
    ):
        return apply_certified_live_merit(
            enabled=enabled,
            legacy_score=(
                legacy_score
                or self.legacy_score()
            ),
            evidence_bundle=(
                bundle
            ),
            media_item_id=(
                media_item_id
            ),
            certificate_path=(
                certificate_path
            ),
            connection_factory=(
                self.connection_factory
            ),
            badge_resolver=(
                badge
            ),
        )

    def test_version_and_pinned_certificate(
        self,
    ):
        self.assertEqual(
            LIVE_MERIT_RELEASE_RUNTIME_VERSION,
            "live-merit-release-runtime-v1",
        )

        payload = json.loads(
            CERTIFICATE_PATH.read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(
            payload[
                "certificate_sha256"
            ],
            LIVE_MERIT_RELEASE_REQUIRED_CERTIFICATE_SHA256,
        )

    def test_direct_stakeholder_positive_applies_plus_six(
        self,
    ):
        seeded = (
            self.seed_direct_positive()
        )

        result = self.apply(
            bundle=seeded[
                "bundle"
            ],
            media_item_id=seeded[
                "media_item_id"
            ],
        )

        self.assertEqual(
            result[
                "status"
            ],
            "applied",
        )
        self.assertTrue(
            result[
                "score_effect_applied"
            ]
        )
        self.assertEqual(
            result[
                "adjustment"
            ],
            6.0,
        )
        self.assertEqual(
            result[
                "score"
            ][
                "total"
            ],
            66,
        )
        self.assertTrue(
            result[
                "strict_independence"
            ][
                "verified"
            ]
        )
        self.assertEqual(
            result[
                "score"
            ][
                "components"
            ][
                "certified_corroboration_overlay"
            ],
            6.0,
        )

    def test_direct_stakeholder_positive_clamps_at_100(
        self,
    ):
        seeded = (
            self.seed_direct_positive(
                media_item_id=(
                    "media-live-clamp"
                )
            )
        )

        result = self.apply(
            bundle=seeded[
                "bundle"
            ],
            media_item_id=seeded[
                "media_item_id"
            ],
            legacy_score=(
                self.legacy_score(
                    98
                )
            ),
        )

        self.assertEqual(
            result[
                "score"
            ][
                "total"
            ],
            100,
        )

    def test_disabled_runtime_preserves_exact_legacy_score(
        self,
    ):
        seeded = (
            self.seed_direct_positive(
                media_item_id=(
                    "media-disabled"
                )
            )
        )

        legacy = (
            self.legacy_score()
        )

        result = self.apply(
            bundle=seeded[
                "bundle"
            ],
            media_item_id=seeded[
                "media_item_id"
            ],
            legacy_score=legacy,
            enabled=False,
        )

        self.assertFalse(
            result[
                "score_effect_applied"
            ]
        )
        self.assertEqual(
            result[
                "score"
            ],
            legacy,
        )

    def test_missing_certificate_fails_closed(
        self,
    ):
        seeded = (
            self.seed_direct_positive(
                media_item_id=(
                    "media-missing-cert"
                )
            )
        )

        legacy = (
            self.legacy_score()
        )

        missing = (
            Path(
                self.temp.name
            )
            / "missing.json"
        )

        result = self.apply(
            bundle=seeded[
                "bundle"
            ],
            media_item_id=seeded[
                "media_item_id"
            ],
            legacy_score=legacy,
            certificate_path=(
                missing
            ),
        )

        self.assertEqual(
            result[
                "score"
            ],
            legacy,
        )
        self.assertIn(
            "certificate_invalid",
            result[
                "reason"
            ],
        )

    def test_tampered_certificate_fails_closed(
        self,
    ):
        seeded = (
            self.seed_direct_positive(
                media_item_id=(
                    "media-tampered-cert"
                )
            )
        )

        payload = json.loads(
            CERTIFICATE_PATH.read_text(
                encoding="utf-8"
            )
        )

        payload[
            "cases"
        ][
            0
        ][
            "expectations"
        ][
            "adjustment"
        ] = 5.0

        tampered = (
            Path(
                self.temp.name
            )
            / "tampered.json"
        )

        tampered.write_text(
            json.dumps(
                payload,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        legacy = (
            self.legacy_score()
        )

        result = self.apply(
            bundle=seeded[
                "bundle"
            ],
            media_item_id=seeded[
                "media_item_id"
            ],
            legacy_score=legacy,
            certificate_path=(
                tampered
            ),
        )

        self.assertEqual(
            result[
                "score"
            ],
            legacy,
        )

    def test_different_authorized_certificate_identity_fails_closed(
        self,
    ):
        seeded = (
            self.seed_direct_positive(
                media_item_id=(
                    "media-alternate-cert"
                )
            )
        )

        payload = json.loads(
            CERTIFICATE_PATH.read_text(
                encoding="utf-8"
            )
        )

        cases = copy.deepcopy(
            payload[
                "cases"
            ]
        )

        cases[
            0
        ][
            "source_captures"
        ][
            0
        ][
            "content_sha256"
        ] = (
            "a"
            * 64
        )

        alternate = (
            build_merit_score_release_certificate(
                cases=cases
            )
        )

        self.assertEqual(
            alternate[
                "status"
            ],
            "authorized",
        )

        self.assertNotEqual(
            alternate[
                "certificate_sha256"
            ],
            LIVE_MERIT_RELEASE_REQUIRED_CERTIFICATE_SHA256,
        )

        path = (
            Path(
                self.temp.name
            )
            / "alternate.json"
        )

        path.write_text(
            json.dumps(
                alternate,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        legacy = (
            self.legacy_score()
        )

        result = self.apply(
            bundle=seeded[
                "bundle"
            ],
            media_item_id=seeded[
                "media_item_id"
            ],
            legacy_score=legacy,
            certificate_path=path,
        )

        self.assertFalse(
            result[
                "score_effect_applied"
            ]
        )
        self.assertEqual(
            result[
                "score"
            ],
            legacy,
        )

    def test_model_only_verified_independence_never_gets_live_boost(
        self,
    ):
        media_item_id = (
            "media-model-only"
        )

        bundle = (
            self.synthetic_bundle(
                media_item_id=(
                    media_item_id
                ),
                verified_assertion=True,
            )
        )

        legacy = (
            self.legacy_score()
        )

        result = self.apply(
            bundle=bundle,
            media_item_id=(
                media_item_id
            ),
            legacy_score=(
                legacy
            ),
        )

        self.assertEqual(
            result[
                "signal"
            ],
            "verified_corroboration",
        )
        self.assertFalse(
            result[
                "score_effect_applied"
            ]
        )
        self.assertEqual(
            result[
                "reason"
            ],
            (
                "strict_direct_stakeholder_"
                "lineage_missing"
            ),
        )
        self.assertEqual(
            result[
                "score"
            ],
            legacy,
        )

    def test_dependency_never_gets_live_boost(
        self,
    ):
        media_item_id = (
            "media-dependency"
        )

        result = self.apply(
            bundle=(
                self.synthetic_bundle(
                    media_item_id=(
                        media_item_id
                    ),
                    dependency=True,
                )
            ),
            media_item_id=(
                media_item_id
            ),
        )

        self.assertFalse(
            result[
                "score_effect_applied"
            ]
        )
        self.assertEqual(
            result[
                "signal"
            ],
            "support_dependency_present",
        )

    def test_same_publisher_never_gets_live_boost(
        self,
    ):
        media_item_id = (
            "media-same-publisher"
        )

        result = self.apply(
            bundle=(
                self.synthetic_bundle(
                    media_item_id=(
                        media_item_id
                    ),
                    same_source=True,
                )
            ),
            media_item_id=(
                media_item_id
            ),
        )

        self.assertFalse(
            result[
                "score_effect_applied"
            ]
        )
        self.assertEqual(
            result[
                "signal"
            ],
            "no_verified_corroboration_boost",
        )

    def test_contested_verified_support_never_gets_live_boost(
        self,
    ):
        seeded = (
            self.seed_direct_positive(
                media_item_id=(
                    "media-contested"
                )
            )
        )

        bundle = copy.deepcopy(
            seeded[
                "bundle"
            ]
        )

        bundle[
            "claim_links"
        ].append(
            {
                "id": (
                    "contradiction-link"
                ),
                "claim_id": (
                    seeded[
                        "claim"
                    ][
                        "id"
                    ]
                ),
                "target_type": (
                    "source_observation"
                ),
                "target_id": (
                    bundle[
                        "source_observations"
                    ][
                        1
                    ][
                        "id"
                    ]
                ),
                "relationship_type": (
                    "contradicts"
                ),
                "confidence": 0.99,
                "observed_at": (
                    "2026-08-16T04:20:00Z"
                ),
            }
        )

        result = self.apply(
            bundle=bundle,
            media_item_id=(
                seeded[
                    "media_item_id"
                ]
            ),
        )

        self.assertFalse(
            result[
                "score_effect_applied"
            ]
        )
        self.assertEqual(
            result[
                "signal"
            ],
            (
                "verified_corroboration_"
                "contested"
            ),
        )

    def test_primary_claim_must_be_unique(
        self,
    ):
        media_item_id = (
            "media-duplicate"
        )

        bundle = (
            self.synthetic_bundle(
                media_item_id=(
                    media_item_id
                ),
            )
        )

        duplicate = copy.deepcopy(
            bundle[
                "claims"
            ][
                0
            ]
        )

        duplicate[
            "id"
        ] = "duplicate-id"

        duplicate[
            "canonical_key"
        ] = (
            "article-primary|"
            + media_item_id
            + "|duplicate"
        )

        bundle[
            "claims"
        ].append(
            duplicate
        )

        result = self.apply(
            bundle=bundle,
            media_item_id=(
                media_item_id
            ),
        )

        self.assertFalse(
            result[
                "score_effect_applied"
            ]
        )
        self.assertEqual(
            result[
                "reason"
            ],
            "primary_claim_not_unique",
        )

    def test_cache_token_changes_when_certificate_changes(
        self,
    ):
        original = (
            live_merit_release_cache_token(
                enabled=True,
                certificate_path=(
                    CERTIFICATE_PATH
                ),
            )
        )

        copy_path = (
            Path(
                self.temp.name
            )
            / "certificate.json"
        )

        copy_path.write_bytes(
            CERTIFICATE_PATH.read_bytes()
        )

        copied = (
            live_merit_release_cache_token(
                enabled=True,
                certificate_path=(
                    copy_path
                ),
            )
        )

        self.assertEqual(
            original,
            copied,
        )

        with copy_path.open(
            "ab"
        ) as handle:
            handle.write(
                b"\n"
            )

        changed = (
            live_merit_release_cache_token(
                enabled=True,
                certificate_path=(
                    copy_path
                ),
            )
        )

        self.assertNotEqual(
            copied,
            changed,
        )


if __name__ == "__main__":
    unittest.main()

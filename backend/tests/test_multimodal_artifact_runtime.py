import unittest

from app.models import artifacts as artifact_models
from app.models import content
from app.services import (
    artifact_extraction,
    multimodal_extraction,
)


OBSERVED = "2026-08-16T12:00:00Z"


def provenance(
    url="https://example.com/source",
):
    return content.ProvenanceRecord(
        source_url=url,
        observed_at=OBSERVED,
        extraction_method="browser_dom",
        content_hash="source-hash",
    )


def text_component(
    component_id,
    role,
    text,
):
    return content.TextComponent(
        component_id=component_id,
        role=role,
        text=text,
        provenance=provenance(),
    )


def media_component(
    component_id,
    media_kind,
    *,
    media_url="https://cdn.example/media",
    duration_seconds=None,
    width=None,
    height=None,
    has_audio=None,
):
    return content.MediaComponent(
        component_id=component_id,
        media_kind=media_kind,
        media_url=media_url,
        duration_seconds=duration_seconds,
        width=width,
        height=height,
        has_audio=has_audio,
        provenance=provenance(),
    )


def make_item(
    *,
    item_id="x:123",
    platform="x",
    surface="post",
    container_kind="post",
    texts=None,
    media=None,
):
    item = content.UnifiedContentItem(
        item_id=item_id,
        platform=platform,
        platform_surface=surface,
        container_kind=container_kind,
        canonical_url=(
            "https://example.com/content"
        ),
        observed_at=OBSERVED,
        text_components=list(
            texts or []
        ),
        media_components=list(
            media or []
        ),
    )

    content.validate_unified_content_item(
        item
    )

    return item


def operations(manifest):
    return [
        work.operation
        for work in manifest.work_units
    ]


def recursive_keys(value):
    keys = set()

    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(
                str(key).lower()
            )

            keys.update(
                recursive_keys(child)
            )

    elif isinstance(value, (list, tuple)):
        for child in value:
            keys.update(
                recursive_keys(child)
            )

    return keys


class MultimodalArtifactRuntimeTests(
    unittest.TestCase
):
    def test_text_artifacts_are_deterministic_and_hashed(
        self,
    ):
        item = make_item(
            texts=[
                text_component(
                    "title",
                    "title",
                    "Transfer update",
                ),
                text_component(
                    "body",
                    "body",
                    "Body text",
                ),
            ]
        )

        first = (
            artifact_extraction
            .materialize_item_artifacts(
                item
            )
        )

        second = (
            artifact_extraction
            .materialize_item_artifacts(
                item
            )
        )

        self.assertEqual(
            [
                artifact.artifact_id
                for artifact
                in first.artifacts
            ],
            [
                artifact.artifact_id
                for artifact
                in second.artifacts
            ],
        )

        self.assertEqual(
            [
                artifact.content_hash
                for artifact
                in first.artifacts
            ],
            [
                artifact.content_hash
                for artifact
                in second.artifacts
            ],
        )

        self.assertEqual(
            [
                artifact.artifact_kind
                for artifact
                in first.artifacts
            ],
            [
                "text_component",
                "text_component",
            ],
        )

        self.assertEqual(
            first.artifacts[
                1
            ].payload["text"],
            "Body text",
        )


    def test_media_reference_preserves_structural_media_metadata(
        self,
    ):
        item = make_item(
            texts=[
                text_component(
                    "caption",
                    "caption",
                    "Clip",
                )
            ],
            media=[
                media_component(
                    "video:0",
                    "video",
                    media_url=(
                        "https://cdn.example/"
                        "video.mp4"
                    ),
                    duration_seconds=44,
                    width=1080,
                    height=1920,
                    has_audio=True,
                )
            ],
        )

        manifest = (
            artifact_extraction
            .materialize_item_artifacts(
                item
            )
        )

        media_artifact = next(
            artifact
            for artifact
            in manifest.artifacts
            if artifact.artifact_kind
            == "media_reference"
        )

        self.assertEqual(
            media_artifact.payload[
                "media_url"
            ],
            "https://cdn.example/video.mp4",
        )

        self.assertEqual(
            media_artifact.payload[
                "duration_seconds"
            ],
            44.0,
        )

        self.assertEqual(
            media_artifact.payload[
                "width"
            ],
            1080,
        )

        self.assertEqual(
            media_artifact.payload[
                "height"
            ],
            1920,
        )

        self.assertTrue(
            media_artifact.payload[
                "has_audio"
            ]
        )


    def test_short_video_schedule_is_bounded_and_deterministic(
        self,
    ):
        media = media_component(
            "video:0",
            "video",
            duration_seconds=44,
        )

        schedule = (
            artifact_extraction
            .frame_sampling_schedule(
                media
            )
        )

        self.assertEqual(
            schedule["strategy"],
            "uniform_short_video",
        )

        self.assertEqual(
            schedule[
                "timestamps_seconds"
            ],
            [
                0.0,
                8.8,
                17.6,
                26.4,
                35.2,
                43.12,
            ],
        )

        self.assertEqual(
            schedule["sample_limit"],
            6,
        )

        self.assertFalse(
            schedule[
                "requires_duration_probe"
            ]
        )


    def test_long_video_schedule_is_stratified_and_bounded(
        self,
    ):
        media = media_component(
            "video:0",
            "video",
            duration_seconds=600,
        )

        schedule = (
            artifact_extraction
            .frame_sampling_schedule(
                media
            )
        )

        self.assertEqual(
            schedule["strategy"],
            "stratified_long_video",
        )

        self.assertEqual(
            len(
                schedule[
                    "timestamps_seconds"
                ]
            ),
            9,
        )

        self.assertEqual(
            schedule[
                "timestamps_seconds"
            ][0],
            12.0,
        )

        self.assertEqual(
            schedule[
                "timestamps_seconds"
            ][-1],
            588.0,
        )

        self.assertEqual(
            schedule["sample_limit"],
            9,
        )


    def test_unknown_duration_requires_probe_without_guessing_timestamp(
        self,
    ):
        media = media_component(
            "video:0",
            "video",
            duration_seconds=None,
        )

        schedule = (
            artifact_extraction
            .frame_sampling_schedule(
                media
            )
        )

        self.assertEqual(
            schedule["strategy"],
            "duration_probe_then_sample",
        )

        self.assertEqual(
            schedule[
                "timestamps_seconds"
            ],
            [],
        )

        self.assertTrue(
            schedule[
                "requires_duration_probe"
            ]
        )


    def test_image_creates_visual_and_ocr_work(
        self,
    ):
        item = make_item(
            texts=[
                text_component(
                    "caption",
                    "caption",
                    "Photo",
                )
            ],
            media=[
                media_component(
                    "image:0",
                    "image",
                )
            ],
        )

        manifest = (
            artifact_extraction
            .materialize_item_artifacts(
                item
            )
        )

        self.assertIn(
            "image_visual",
            operations(manifest),
        )

        self.assertIn(
            "ocr",
            operations(manifest),
        )

        self.assertNotIn(
            "transcription",
            operations(manifest),
        )

        self.assertNotIn(
            "video_frame_extract",
            operations(manifest),
        )


    def test_video_ocr_depends_on_frame_extraction_and_transcription_is_separate(
        self,
    ):
        item = make_item(
            texts=[
                text_component(
                    "caption",
                    "caption",
                    "Video",
                )
            ],
            media=[
                media_component(
                    "video:0",
                    "video",
                    duration_seconds=60,
                    has_audio=True,
                )
            ],
        )

        manifest = (
            artifact_extraction
            .materialize_item_artifacts(
                item
            )
        )

        frame = next(
            work
            for work
            in manifest.work_units
            if work.operation
            == "video_frame_extract"
        )

        ocr = next(
            work
            for work
            in manifest.work_units
            if work.operation
            == "ocr"
        )

        transcription = next(
            work
            for work
            in manifest.work_units
            if work.operation
            == "transcription"
        )

        self.assertIn(
            frame.work_id,
            ocr.depends_on_work_ids,
        )

        self.assertNotEqual(
            frame.work_id,
            transcription.work_id,
        )


    def test_existing_transcript_and_ocr_text_suppress_redundant_work(
        self,
    ):
        item = make_item(
            texts=[
                text_component(
                    "transcript",
                    "transcript",
                    "Spoken words",
                ),
                text_component(
                    "on_screen_text",
                    "on_screen_text",
                    "Score 2-1",
                ),
            ],
            media=[
                media_component(
                    "video:0",
                    "video",
                    duration_seconds=60,
                    has_audio=True,
                )
            ],
        )

        plan = (
            multimodal_extraction
            .plan_content_item(
                item
            )
        )

        self.assertEqual(
            plan.transcription_component_ids,
            (),
        )

        self.assertEqual(
            plan.ocr_component_ids,
            (),
        )

        manifest = (
            artifact_extraction
            .materialize_item_artifacts(
                item,
                plan=plan,
            )
        )

        self.assertNotIn(
            "transcription",
            operations(manifest),
        )

        self.assertNotIn(
            "ocr",
            operations(manifest),
        )

        self.assertIn(
            "video_frame_extract",
            operations(manifest),
        )


    def test_caption_alignment_waits_for_available_media_work(
        self,
    ):
        item = make_item(
            texts=[
                text_component(
                    "caption",
                    "caption",
                    "Caption",
                )
            ],
            media=[
                media_component(
                    "video:0",
                    "video",
                    duration_seconds=30,
                    has_audio=True,
                )
            ],
        )

        manifest = (
            artifact_extraction
            .materialize_item_artifacts(
                item
            )
        )

        alignment = next(
            work
            for work
            in manifest.work_units
            if work.operation
            == "caption_media_alignment"
        )

        dependency_operations = {
            work.operation
            for work
            in manifest.work_units
            if work.work_id
            in alignment.depends_on_work_ids
        }

        self.assertEqual(
            dependency_operations,
            {
                "video_frame_extract",
                "ocr",
                "transcription",
            },
        )

        self.assertEqual(
            alignment.source_component_ids,
            [
                "caption",
                "video:0",
            ],
        )


    def test_thread_like_item_creates_conversation_traversal_work(
        self,
    ):
        item = make_item(
            surface="comment",
            container_kind="comment",
            texts=[
                text_component(
                    "comment",
                    "comment",
                    "Reply text",
                )
            ],
        )

        manifest = (
            artifact_extraction
            .materialize_item_artifacts(
                item
            )
        )

        traversal = next(
            work
            for work
            in manifest.work_units
            if work.operation
            == "conversation_traversal"
        )

        self.assertEqual(
            traversal.strategy,
            "platform_relationship_discovery",
        )


    def test_bundle_materializes_dependency_and_conversation_relationship_work(
        self,
    ):
        first = make_item(
            item_id="x:1",
            texts=[
                text_component(
                    "body",
                    "body",
                    "One",
                )
            ],
        )

        second = make_item(
            item_id="x:2",
            texts=[
                text_component(
                    "body",
                    "body",
                    "Two",
                )
            ],
        )

        third = make_item(
            item_id="x:3",
            texts=[
                text_component(
                    "reply",
                    "reply",
                    "Three",
                )
            ],
            surface="reply",
            container_kind="reply",
        )

        bundle = (
            content
            .UnifiedContentBundle(
                bundle_id="bundle:1",
                root_item_ids=[
                    "x:1"
                ],
                items=[
                    first,
                    second,
                    third,
                ],
                relationships=[
                    content.ContentRelationship(
                        relationship_id=(
                            "rel:quote"
                        ),
                        source_item_id="x:1",
                        target_item_id="x:2",
                        relationship_type=(
                            "quote_of"
                        ),
                        provenance=provenance(),
                    ),
                    content.ContentRelationship(
                        relationship_id=(
                            "rel:reply"
                        ),
                        source_item_id="x:3",
                        target_item_id="x:1",
                        relationship_type=(
                            "reply_to"
                        ),
                        provenance=provenance(),
                    ),
                ],
            )
        )

        content.validate_unified_content_bundle(
            bundle
        )

        manifest = (
            artifact_extraction
            .materialize_bundle_artifacts(
                bundle
            )
        )

        self.assertEqual(
            len(
                manifest.item_manifests
            ),
            3,
        )

        self.assertEqual(
            {
                work.operation
                for work
                in manifest.work_units
            },
            {
                "dependency_trace",
                "conversation_traversal",
            },
        )


    def test_generated_manifest_never_creates_semantic_intelligence_fields(
        self,
    ):
        item = make_item(
            texts=[
                text_component(
                    "caption",
                    "caption",
                    "Caption",
                )
            ],
            media=[
                media_component(
                    "image:0",
                    "image",
                )
            ],
        )

        manifest = (
            artifact_extraction
            .materialize_item_artifacts(
                item
            )
        )

        payload = (
            manifest.model_dump(
                mode="json"
            )
            if hasattr(
                manifest,
                "model_dump",
            )
            else manifest.dict()
        )

        keys = recursive_keys(
            payload
        )

        for forbidden in (
            "merit_score",
            "truth_status",
            "authority",
            "authority_score",
            "training_eligible",
            "independence_status",
            "affects_merit_score",
        ):
            self.assertNotIn(
                forbidden,
                keys,
            )


    def test_manifest_validation_rejects_unknown_work_dependency(
        self,
    ):
        manifest = (
            artifact_models
            .ItemArtifactManifest(
                item_id="x:1",
                work_units=[
                    artifact_models
                    .ArtifactWorkUnit(
                        work_id="work:1",
                        operation="ocr",
                        depends_on_work_ids=[
                            "work:missing"
                        ],
                    )
                ],
            )
        )

        with self.assertRaises(
            ValueError
        ):
            (
                artifact_models
                .validate_item_artifact_manifest(
                    manifest
                )
            )


    def test_executor_without_provider_leaves_work_pending_and_input_unchanged(
        self,
    ):
        item = make_item(
            texts=[
                text_component(
                    "caption",
                    "caption",
                    "Photo",
                )
            ],
            media=[
                media_component(
                    "image:0",
                    "image",
                )
            ],
        )

        manifest = (
            artifact_extraction
            .materialize_item_artifacts(
                item
            )
        )

        result = (
            artifact_extraction
            .execute_item_artifact_manifest(
                manifest,
                executors={},
            )
        )

        self.assertTrue(
            all(
                work.status == "pending"
                for work
                in result.work_units
            )
        )

        self.assertTrue(
            all(
                work.status == "pending"
                for work
                in manifest.work_units
            )
        )

        self.assertEqual(
            len(result.artifacts),
            len(manifest.artifacts),
        )


    def test_executor_runs_dependencies_and_materializes_outputs(
        self,
    ):
        item = make_item(
            texts=[
                text_component(
                    "caption",
                    "caption",
                    "Video",
                )
            ],
            media=[
                media_component(
                    "video:0",
                    "video",
                    duration_seconds=20,
                    has_audio=False,
                )
            ],
        )

        manifest = (
            artifact_extraction
            .materialize_item_artifacts(
                item
            )
        )

        def frames(
            work,
            _artifacts,
            _dependencies,
        ):
            return {
                "artifact_kind": "frame",
                "modality": "image",
                "payload": {
                    "timestamp_seconds": 5.0
                },
            }

        def ocr(
            work,
            _artifacts,
            dependencies,
        ):
            self.assertTrue(
                dependencies
            )

            return {
                "artifact_kind": (
                    "ocr_text"
                ),
                "modality": "text",
                "payload": {
                    "text": "Score 2-1"
                },
            }

        def alignment(
            work,
            _artifacts,
            dependencies,
        ):
            self.assertTrue(
                dependencies
            )

            return {
                "artifact_kind": (
                    "alignment_input"
                ),
                "modality": (
                    "multimodal"
                ),
                "payload": {
                    "component_ids": (
                        work
                        .source_component_ids
                    )
                },
            }

        result = (
            artifact_extraction
            .execute_item_artifact_manifest(
                manifest,
                executors={
                    (
                        "video_frame_"
                        "extract"
                    ): frames,
                    "ocr": ocr,
                    (
                        "caption_media_"
                        "alignment"
                    ): alignment,
                },
            )
        )

        statuses = {
            work.operation: work.status
            for work
            in result.work_units
        }

        self.assertEqual(
            statuses[
                "video_frame_extract"
            ],
            "completed",
        )

        self.assertEqual(
            statuses[
                "ocr"
            ],
            "completed",
        )

        self.assertEqual(
            statuses[
                "caption_media_alignment"
            ],
            "completed",
        )

        self.assertEqual(
            statuses[
                "video_visual"
            ],
            "pending",
        )

        self.assertEqual(
            statuses[
                "multimodal_semantic_fusion"
            ],
            "pending",
        )

        kinds = {
            artifact.artifact_kind
            for artifact
            in result.artifacts
        }

        self.assertTrue(
            {
                "frame",
                "ocr_text",
                "alignment_input",
            }.issubset(kinds)
        )


    def test_executor_semantic_smuggling_fails_closed(
        self,
    ):
        item = make_item(
            texts=[
                text_component(
                    "body",
                    "body",
                    "Photo",
                )
            ],
            media=[
                media_component(
                    "image:0",
                    "image",
                )
            ],
        )

        manifest = (
            artifact_extraction
            .materialize_item_artifacts(
                item
            )
        )

        def unsafe(
            _work,
            _artifacts,
            _dependencies,
        ):
            return {
                "artifact_kind": "visual",
                "modality": "image",
                "payload": {
                    "authority": "official"
                },
            }

        result = (
            artifact_extraction
            .execute_item_artifact_manifest(
                manifest,
                executors={
                    "image_visual": unsafe
                },
            )
        )

        visual = next(
            work
            for work
            in result.work_units
            if work.operation
            == "image_visual"
        )

        self.assertEqual(
            visual.status,
            "unavailable",
        )

        self.assertEqual(
            visual.output_artifact_ids,
            [],
        )

        self.assertEqual(
            visual.metadata[
                "failure_type"
            ],
            "ValueError",
        )


if __name__ == "__main__":
    unittest.main()
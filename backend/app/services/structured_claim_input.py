from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Dict, Mapping

from app.models import artifacts as artifact_models


STRUCTURED_CLAIM_INPUT_VERSION = "structured-claim-input-v1"
STRUCTURED_CLAIM_METADATA_FIELD = (
    "structured_claim_outputs_by_candidate_id"
)

STRUCTURED_CLAIM_INPUT_POLICY = {
    "reads_claim_candidate_metadata_sidecar_only": True,
    "outputs_are_keyed_by_existing_candidate_id": True,
    "candidate_ids_are_never_generated_here": True,
    "claim_candidate_payload_is_not_modified": True,
    "structured_semantics_are_not_validated_here": True,
    "downstream_claim_intelligence_owns_semantic_validation": True,
    "duplicate_candidate_ids_fail_closed": True,
    "unbound_sidecar_outputs_are_ignored": True,
    "raw_provider_response_stored": False,
    "bounded_structured_proposal_forwarded": True,
    "establishes_identity": False,
    "establishes_truth": False,
    "establishes_authority": False,
    "establishes_reliability": False,
    "establishes_independence": False,
    "establishes_corroboration": False,
    "affects_live_merit": False,
    "provider_calls_expected": 0,
    "provider_tokens_expected": 0,
    "database_writes_expected": 0,
}


class StructuredClaimInputError(ValueError):
    pass


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def collect_structured_claim_outputs(
    manifest: artifact_models.ItemArtifactManifest,
) -> Dict[str, Any]:
    """Collect bounded structured proposals from claim-candidate sidecar metadata.

    Correlation is the only responsibility here. This function never parses,
    repairs, normalizes, or assigns claim semantics or identity.
    """

    if not isinstance(manifest, artifact_models.ItemArtifactManifest):
        raise StructuredClaimInputError(
            "manifest must be an ItemArtifactManifest."
        )

    artifact_models.validate_item_artifact_manifest(manifest)

    rows = []
    occurrences: Dict[str, int] = {}
    pending_outputs: Dict[str, Any] = {}
    unbound_output_ids = []
    report_errors = []

    for artifact in manifest.artifacts:
        if artifact.artifact_kind != "claim_candidates":
            continue

        raw_candidates = artifact.payload.get("candidates", [])

        if not isinstance(raw_candidates, list):
            report_errors.append(
                "claim_candidates_payload_not_list:"
                + _clean(artifact.artifact_id)
            )
            continue

        container_ids = []

        for index, raw_candidate in enumerate(raw_candidates):
            if not isinstance(raw_candidate, Mapping):
                report_errors.append(
                    "candidate_not_mapping:"
                    + _clean(artifact.artifact_id)
                    + ":"
                    + str(index)
                )
                continue

            candidate_id = _clean(raw_candidate.get("candidate_id"))

            if not candidate_id:
                report_errors.append(
                    "candidate_id_missing:"
                    + _clean(artifact.artifact_id)
                    + ":"
                    + str(index)
                )
                continue

            occurrences[candidate_id] = occurrences.get(candidate_id, 0) + 1
            container_ids.append(candidate_id)

        raw_sidecar = artifact.metadata.get(
            STRUCTURED_CLAIM_METADATA_FIELD
        )

        if raw_sidecar is None:
            sidecar: Mapping[str, Any] = {}
        elif isinstance(raw_sidecar, Mapping):
            sidecar = raw_sidecar
        else:
            report_errors.append(
                "structured_claim_sidecar_not_mapping:"
                + _clean(artifact.artifact_id)
            )
            sidecar = {}

        normalized_sidecar: Dict[str, Any] = {}
        sidecar_duplicate_ids = []

        for raw_id, raw_output in sidecar.items():
            candidate_id = _clean(raw_id)

            if not candidate_id:
                report_errors.append(
                    "empty_structured_output_candidate_id:"
                    + _clean(artifact.artifact_id)
                )
                continue

            if candidate_id in normalized_sidecar:
                sidecar_duplicate_ids.append(candidate_id)
                continue

            normalized_sidecar[candidate_id] = deepcopy(raw_output)

        for candidate_id in sorted(set(sidecar_duplicate_ids)):
            normalized_sidecar.pop(candidate_id, None)
            report_errors.append(
                "duplicate_sidecar_candidate_id:"
                + candidate_id
            )

        container_id_set = set(container_ids)

        for candidate_id in sorted(normalized_sidecar):
            if candidate_id not in container_id_set:
                unbound_output_ids.append(candidate_id)
                report_errors.append(
                    "unbound_structured_output_candidate_id:"
                    + candidate_id
                )
                continue

            pending_outputs[candidate_id] = normalized_sidecar[candidate_id]

        for candidate_id in container_ids:
            output_present = candidate_id in normalized_sidecar
            output_value = normalized_sidecar.get(candidate_id)

            rows.append(
                {
                    "candidate_id": candidate_id,
                    "candidate_container_artifact_id": _clean(
                        artifact.artifact_id
                    ),
                    "structured_output_present": output_present,
                    "structured_output_type": (
                        type(output_value).__name__
                        if output_present
                        else ""
                    ),
                    "status": (
                        "provided"
                        if output_present
                        else "not_provided"
                    ),
                }
            )

    duplicate_ids = sorted(
        candidate_id
        for candidate_id, count in occurrences.items()
        if count > 1
    )

    duplicate_set = set(duplicate_ids)

    for candidate_id in duplicate_ids:
        pending_outputs.pop(candidate_id, None)
        report_errors.append(
            "duplicate_candidate_id:"
            + candidate_id
        )

    for row in rows:
        if row["candidate_id"] in duplicate_set:
            row["status"] = "duplicate_candidate_id"

    outputs = {
        candidate_id: pending_outputs[candidate_id]
        for candidate_id in sorted(pending_outputs)
        if candidate_id not in duplicate_set
    }

    return {
        "version": STRUCTURED_CLAIM_INPUT_VERSION,
        "item_id": manifest.item_id,
        "outputs_by_candidate_id": outputs,
        "candidate_rows": rows,
        "candidate_count": len(rows),
        "provided_count": len(outputs),
        "duplicate_candidate_ids": duplicate_ids,
        "unbound_output_candidate_ids": sorted(set(unbound_output_ids)),
        "report_errors": report_errors,
        "raw_provider_response_stored": False,
        "provider_call_performed": False,
        "database_write_performed": False,
        "policy": dict(STRUCTURED_CLAIM_INPUT_POLICY),
    }


def structured_claim_input_descriptor() -> Dict[str, Any]:
    return {
        "version": STRUCTURED_CLAIM_INPUT_VERSION,
        "metadata_field": STRUCTURED_CLAIM_METADATA_FIELD,
        "provider_call_performed": False,
        "provider_calls_expected": 0,
        "provider_tokens_expected": 0,
        "database_writes_expected": 0,
        "establishes_identity": False,
        "live_merit_effect": False,
        "policy": dict(STRUCTURED_CLAIM_INPUT_POLICY),
    }


__all__ = [
    "STRUCTURED_CLAIM_INPUT_VERSION",
    "STRUCTURED_CLAIM_METADATA_FIELD",
    "STRUCTURED_CLAIM_INPUT_POLICY",
    "StructuredClaimInputError",
    "collect_structured_claim_outputs",
    "structured_claim_input_descriptor",
]

from typing import Any, Dict


CLAIM_STANCE_POLICY_VERSION = (
    "claim-stance-v1"
)

CLAIM_LINK_STANCE_RELATIONSHIP_VOCABULARY = (
    "aligned_to",
    "contradicts",
    "supports",
)

CLAIM_STANCE_STATUS_VOCABULARY = (
    "no_explicit_stance",
    "explicit_support",
    "explicit_contradiction",
    "mixed_explicit_stance",
)


def build_claim_stance_analysis(
    bundle: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(
        bundle,
        dict,
    ):
        raise ValueError(
            "Claim stance analysis requires "
            "a dictionary."
        )

    claims_by_id = {}

    for raw_claim in bundle.get(
        "claims",
        [],
    ):
        if not isinstance(
            raw_claim,
            dict,
        ):
            continue

        claim_id = str(
            raw_claim.get("id") or ""
        ).strip()

        if not claim_id:
            continue

        normalized = {
            "claim_id": claim_id,
            "canonical_key": str(
                raw_claim.get(
                    "canonical_key"
                ) or ""
            ).strip(),
            "subject_key": str(
                raw_claim.get(
                    "subject_key"
                ) or ""
            ).strip(),
            "canonical_text": " ".join(
                str(
                    raw_claim.get(
                        "canonical_text"
                    ) or ""
                ).split()
            ),
            "claim_type": str(
                raw_claim.get(
                    "claim_type"
                ) or ""
            ).strip().lower(),
        }

        existing = claims_by_id.get(
            claim_id
        )

        if (
            existing is not None
            and existing != normalized
        ):
            raise ValueError(
                "Claim stance analysis contains "
                "conflicting canonical claim rows "
                f"for {claim_id}."
            )

        claims_by_id[
            claim_id
        ] = normalized

    links_by_claim = {}

    for raw_link in bundle.get(
        "claim_links",
        [],
    ):
        if not isinstance(
            raw_link,
            dict,
        ):
            continue

        claim_id = str(
            raw_link.get("claim_id") or ""
        ).strip()

        target_type = str(
            raw_link.get(
                "target_type"
            ) or ""
        ).strip().lower()

        target_id = str(
            raw_link.get(
                "target_id"
            ) or ""
        ).strip()

        relationship_type = str(
            raw_link.get(
                "relationship_type"
            ) or ""
        ).strip().lower()

        if (
            not claim_id
            or not target_type
            or not target_id
            or not relationship_type
        ):
            continue

        if relationship_type == "supports":
            stance = "support"

        elif (
            relationship_type
            == "contradicts"
        ):
            stance = "contradiction"

        elif (
            relationship_type
            == "aligned_to"
        ):
            stance = "neutral"

        else:
            stance = "unknown"

        normalized_link = {
            "id": str(
                raw_link.get("id") or ""
            ).strip(),
            "claim_id": claim_id,
            "target_type": target_type,
            "target_id": target_id,
            "relationship_type": (
                relationship_type
            ),
            "stance": stance,
            "confidence": (
                raw_link.get("confidence")
            ),
            "observed_at": str(
                raw_link.get(
                    "observed_at"
                ) or ""
            ).strip(),
        }

        links_by_claim.setdefault(
            claim_id,
            [],
        ).append(
            normalized_link
        )

    claim_ids = sorted(
        set(claims_by_id)
        | set(links_by_claim)
    )

    claim_states = []

    for claim_id in claim_ids:
        links = links_by_claim.get(
            claim_id,
            [],
        )

        links = sorted(
            links,
            key=lambda row: (
                row["stance"],
                row["target_type"],
                row["target_id"],
                row["relationship_type"],
                row["observed_at"],
                str(row["confidence"]),
                row["id"],
            ),
        )

        support_links = [
            row
            for row in links
            if row["stance"] == "support"
        ]

        contradiction_links = [
            row
            for row in links
            if row["stance"]
            == "contradiction"
        ]

        neutral_links = [
            row
            for row in links
            if row["stance"] == "neutral"
        ]

        unknown_links = [
            row
            for row in links
            if row["stance"] == "unknown"
        ]

        if (
            support_links
            and contradiction_links
        ):
            status = (
                "mixed_explicit_stance"
            )

        elif support_links:
            status = (
                "explicit_support"
            )

        elif contradiction_links:
            status = (
                "explicit_contradiction"
            )

        else:
            status = (
                "no_explicit_stance"
            )

        claim = claims_by_id.get(
            claim_id,
            {
                "claim_id": claim_id,
                "canonical_key": "",
                "subject_key": "",
                "canonical_text": "",
                "claim_type": "",
            },
        )

        claim_states.append(
            {
                **claim,
                "status": status,
                "support_links": (
                    support_links
                ),
                "contradiction_links": (
                    contradiction_links
                ),
                "neutral_alignment_links": (
                    neutral_links
                ),
                "unknown_relationship_links": (
                    unknown_links
                ),
                "counts": {
                    "support_links": len(
                        support_links
                    ),
                    "contradiction_links": len(
                        contradiction_links
                    ),
                    "neutral_alignment_links": len(
                        neutral_links
                    ),
                    "unknown_relationship_links": len(
                        unknown_links
                    ),
                },
            }
        )

    return {
        "version": (
            CLAIM_STANCE_POLICY_VERSION
        ),
        "relationship_vocabulary": list(
            CLAIM_LINK_STANCE_RELATIONSHIP_VOCABULARY
        ),
        "status_vocabulary": list(
            CLAIM_STANCE_STATUS_VOCABULARY
        ),
        "policy": {
            "aligned_to_is_neutral": True,
            (
                "unknown_relationship_does_not_"
                "imply_stance"
            ): True,
            (
                "explicit_stance_does_not_"
                "establish_truth"
            ): True,
            (
                "explicit_stance_does_not_"
                "establish_corroboration"
            ): True,
            (
                "support_and_contradiction_are_"
                "historical_edges"
            ): True,
        },
        "claims": claim_states,
    }

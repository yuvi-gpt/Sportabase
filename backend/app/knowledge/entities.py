import hashlib
import json
import re
import unicodedata

from datetime import (
    datetime,
    timezone,
)

from typing import (
    Any,
    Dict,
    Optional,
)


CANONICAL_ENTITY_VERSION = (
    "canonical-entity-v1"
)

ENTITY_ALIAS_VERSION = (
    "entity-alias-v1"
)

ENTITY_RESOLUTION_VERSION = (
    "entity-resolution-v1"
)


ENTITY_TYPES = (
    "player",
    "club",
    "team",
    "league",
    "competition",
    "country",
    "governing_body",
    "reporter",
    "channel",
    "organization",
    "person",
)


ENTITY_ALIAS_TYPES = (
    "canonical_name",
    "common_name",
    "short_name",
    "abbreviation",
    "former_name",
    "handle",
    "external_name",
)


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _key(
    value: Any,
) -> str:
    return _clean(
        value
    ).casefold()


def _canonical_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def normalize_entity_alias(
    value: Any,
) -> str:
    text = _clean(
        value
    )

    if not text:
        return ""

    text = unicodedata.normalize(
        "NFKC",
        text,
    ).casefold()

    output = []

    for character in text:
        if character.isalnum():
            output.append(
                character
            )
        else:
            output.append(
                " "
            )

    return re.sub(
        r"\s+",
        " ",
        "".join(
            output
        ),
    ).strip()


def canonical_entity_id_for_key(
    entity_key: str,
) -> str:
    normalized = _key(
        entity_key
    )

    if not normalized:
        raise ValueError(
            "Canonical entity key is required."
        )

    return hashlib.sha256(
        (
            "canonical-entity|"
            + normalized
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def entity_alias_id_for_record(
    *,
    entity_id: str,
    alias_text: str,
    alias_type: str,
) -> str:
    normalized_entity_id = _clean(
        entity_id
    )

    normalized_alias = (
        normalize_entity_alias(
            alias_text
        )
    )

    normalized_alias_type = _key(
        alias_type
    )

    if not normalized_entity_id:
        raise ValueError(
            "Entity alias entity ID is required."
        )

    if not normalized_alias:
        raise ValueError(
            "Entity alias text is required."
        )

    if (
        normalized_alias_type
        not in ENTITY_ALIAS_TYPES
    ):
        raise ValueError(
            "Entity alias type is unsupported."
        )

    identity = {
        "entity_id": (
            normalized_entity_id
        ),
        "normalized_alias": (
            normalized_alias
        ),
        "alias_type": (
            normalized_alias_type
        ),
    }

    return hashlib.sha256(
        (
            "entity-alias|"
            + _canonical_json(
                identity
            )
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def upsert_canonical_entity(
    *,
    entity_key: str,
    entity_type: str,
    canonical_name: str,
    sport_key: str = "",
    metadata: Optional[
        Dict[str, Any]
    ] = None,
    seen_at: Optional[str] = None,
    connection_factory=None,
) -> Dict[str, Any]:
    if connection_factory is None:
        raise ValueError(
            "Canonical entity persistence "
            "requires database access."
        )

    normalized_key = _key(
        entity_key
    )

    normalized_type = _key(
        entity_type
    )

    normalized_name = _clean(
        canonical_name
    )

    normalized_sport = _key(
        sport_key
    )

    if not normalized_key:
        raise ValueError(
            "Canonical entity key is required."
        )

    if (
        normalized_type
        not in ENTITY_TYPES
    ):
        raise ValueError(
            "Canonical entity type is unsupported."
        )

    if not normalized_name:
        raise ValueError(
            "Canonical entity name is required."
        )

    if (
        metadata is not None
        and not isinstance(
            metadata,
            dict,
        )
    ):
        raise ValueError(
            "Canonical entity metadata "
            "must be a dictionary."
        )

    entity_id = (
        canonical_entity_id_for_key(
            normalized_key
        )
    )

    timestamp = (
        _clean(
            seen_at
        )
        or _now()
    )

    metadata_json = json.dumps(
        metadata or {},
        ensure_ascii=False,
        sort_keys=True,
    )

    conn = connection_factory()

    try:
        existing = conn.execute(
            """
            SELECT *
            FROM canonical_entities
            WHERE entity_key = ?
            """,
            (
                normalized_key,
            ),
        ).fetchone()

        if existing is not None:
            existing = dict(
                existing
            )

            if (
                existing[
                    "id"
                ]
                != entity_id
            ):
                raise ValueError(
                    "Canonical entity key "
                    "has inconsistent identity."
                )

            if (
                _key(
                    existing[
                        "entity_type"
                    ]
                )
                != normalized_type
            ):
                raise ValueError(
                    "Canonical entity type "
                    "cannot change for an "
                    "existing entity key."
                )

            if (
                _key(
                    existing[
                        "sport_key"
                    ]
                )
                != normalized_sport
            ):
                raise ValueError(
                    "Canonical entity sport scope "
                    "cannot change for an "
                    "existing entity key."
                )

        cursor = conn.execute(
            """
            INSERT INTO canonical_entities (
              id,
              entity_key,
              entity_type,
              sport_key,
              canonical_name,
              first_seen_at,
              last_seen_at,
              metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(entity_key)
            DO UPDATE SET
              canonical_name =
                excluded.canonical_name,
              last_seen_at =
                excluded.last_seen_at,
              metadata_json = CASE
                WHEN excluded.metadata_json != '{}'
                THEN excluded.metadata_json
                ELSE canonical_entities.metadata_json
              END
            """,
            (
                entity_id,
                normalized_key,
                normalized_type,
                normalized_sport,
                normalized_name,
                timestamp,
                timestamp,
                metadata_json,
            ),
        )

        created = (
            cursor.rowcount == 1
            and existing is None
        )

        row = conn.execute(
            """
            SELECT *
            FROM canonical_entities
            WHERE id = ?
            """,
            (
                entity_id,
            ),
        ).fetchone()

        conn.commit()

    finally:
        conn.close()

    if row is None:
        raise RuntimeError(
            "Canonical entity persistence failed."
        )

    return {
        "version": (
            CANONICAL_ENTITY_VERSION
        ),
        "entity": dict(
            row
        ),
        "created": created,
        "policy": {
            "entity_identity_is_deterministic": True,
            "entity_key_is_stable_identity": True,
            "entity_type_is_immutable": True,
            "sport_scope_is_immutable": True,
            "entity_record_alone_does_not_establish_authority": True,
            "does_not_change_live_merit": True,
        },
    }


def record_entity_alias(
    *,
    entity_id: str,
    alias_text: str,
    alias_type: str,
    metadata: Optional[
        Dict[str, Any]
    ] = None,
    seen_at: Optional[str] = None,
    connection_factory=None,
) -> Dict[str, Any]:
    if connection_factory is None:
        raise ValueError(
            "Entity alias persistence "
            "requires database access."
        )

    normalized_entity_id = _clean(
        entity_id
    )

    normalized_alias_type = _key(
        alias_type
    )

    normalized_alias = (
        normalize_entity_alias(
            alias_text
        )
    )

    display_alias = _clean(
        alias_text
    )

    if not normalized_entity_id:
        raise ValueError(
            "Entity alias entity ID is required."
        )

    if not normalized_alias:
        raise ValueError(
            "Entity alias text is required."
        )

    if (
        normalized_alias_type
        not in ENTITY_ALIAS_TYPES
    ):
        raise ValueError(
            "Entity alias type is unsupported."
        )

    if (
        metadata is not None
        and not isinstance(
            metadata,
            dict,
        )
    ):
        raise ValueError(
            "Entity alias metadata "
            "must be a dictionary."
        )

    alias_id = (
        entity_alias_id_for_record(
            entity_id=(
                normalized_entity_id
            ),
            alias_text=(
                display_alias
            ),
            alias_type=(
                normalized_alias_type
            ),
        )
    )

    timestamp = (
        _clean(
            seen_at
        )
        or _now()
    )

    metadata_json = json.dumps(
        metadata or {},
        ensure_ascii=False,
        sort_keys=True,
    )

    conn = connection_factory()

    try:
        entity = conn.execute(
            """
            SELECT *
            FROM canonical_entities
            WHERE id = ?
            """,
            (
                normalized_entity_id,
            ),
        ).fetchone()

        if entity is None:
            raise ValueError(
                "Entity alias cannot reference "
                "an unknown canonical entity."
            )

        cursor = conn.execute(
            """
            INSERT INTO entity_aliases (
              id,
              entity_id,
              alias_text,
              normalized_alias,
              alias_type,
              first_seen_at,
              last_seen_at,
              metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id)
            DO UPDATE SET
              alias_text =
                excluded.alias_text,
              last_seen_at =
                excluded.last_seen_at,
              metadata_json = CASE
                WHEN excluded.metadata_json != '{}'
                THEN excluded.metadata_json
                ELSE entity_aliases.metadata_json
              END
            """,
            (
                alias_id,
                normalized_entity_id,
                display_alias,
                normalized_alias,
                normalized_alias_type,
                timestamp,
                timestamp,
                metadata_json,
            ),
        )

        created = (
            cursor.rowcount == 1
            and conn.execute(
                """
                SELECT COUNT(*)
                FROM entity_aliases
                WHERE id = ?
                  AND first_seen_at = last_seen_at
                """,
                (
                    alias_id,
                ),
            ).fetchone()[0]
            == 1
        )

        row = conn.execute(
            """
            SELECT *
            FROM entity_aliases
            WHERE id = ?
            """,
            (
                alias_id,
            ),
        ).fetchone()

        conn.commit()

    finally:
        conn.close()

    if row is None:
        raise RuntimeError(
            "Entity alias persistence failed."
        )

    return {
        "version": (
            ENTITY_ALIAS_VERSION
        ),
        "alias": dict(
            row
        ),
        "created": bool(
            created
        ),
        "policy": {
            "alias_identity_is_deterministic": True,
            "alias_is_candidate_resolution_only": True,
            "alias_does_not_verify_entity_identity": True,
            "alias_does_not_establish_authority": True,
            "does_not_change_live_merit": True,
        },
    }


def resolve_entity_alias(
    *,
    alias_text: str,
    entity_type: str = "",
    sport_key: str = "",
    connection_factory=None,
) -> Dict[str, Any]:
    if connection_factory is None:
        raise ValueError(
            "Entity resolution requires "
            "database access."
        )

    normalized_alias = (
        normalize_entity_alias(
            alias_text
        )
    )

    if not normalized_alias:
        raise ValueError(
            "Entity resolution alias is required."
        )

    normalized_type = _key(
        entity_type
    )

    normalized_sport = _key(
        sport_key
    )

    if (
        normalized_type
        and normalized_type
        not in ENTITY_TYPES
    ):
        raise ValueError(
            "Entity resolution type is unsupported."
        )

    conditions = [
        "a.normalized_alias = ?",
    ]

    parameters = [
        normalized_alias,
    ]

    if normalized_type:
        conditions.append(
            "e.entity_type = ?"
        )

        parameters.append(
            normalized_type
        )

    if normalized_sport:
        conditions.append(
            "e.sport_key = ?"
        )

        parameters.append(
            normalized_sport
        )

    query = """
        SELECT
            e.id AS entity_id,
            e.entity_key,
            e.entity_type,
            e.sport_key,
            e.canonical_name,
            a.id AS alias_id,
            a.alias_text,
            a.alias_type
        FROM entity_aliases AS a
        JOIN canonical_entities AS e
          ON e.id = a.entity_id
        WHERE
    """ + " AND ".join(
        conditions
    ) + """
        ORDER BY
            e.entity_type,
            e.sport_key,
            e.canonical_name,
            e.id,
            a.alias_type,
            a.id
    """

    conn = connection_factory()

    try:
        rows = [
            dict(
                row
            )
            for row
            in conn.execute(
                query,
                tuple(
                    parameters
                ),
            ).fetchall()
        ]

    finally:
        conn.close()

    grouped = {}

    for row in rows:
        entity_id = row[
            "entity_id"
        ]

        candidate = grouped.setdefault(
            entity_id,
            {
                "id": entity_id,
                "entity_key": (
                    row[
                        "entity_key"
                    ]
                ),
                "entity_type": (
                    row[
                        "entity_type"
                    ]
                ),
                "sport_key": (
                    row[
                        "sport_key"
                    ]
                ),
                "canonical_name": (
                    row[
                        "canonical_name"
                    ]
                ),
                "matching_aliases": [],
            },
        )

        candidate[
            "matching_aliases"
        ].append(
            {
                "id": row[
                    "alias_id"
                ],
                "alias_text": (
                    row[
                        "alias_text"
                    ]
                ),
                "alias_type": (
                    row[
                        "alias_type"
                    ]
                ),
            }
        )

    candidates = sorted(
        grouped.values(),
        key=lambda row: (
            row[
                "entity_type"
            ],
            row[
                "sport_key"
            ],
            row[
                "canonical_name"
            ].casefold(),
            row[
                "id"
            ],
        ),
    )

    if not candidates:
        status = "no_match"
        entity = None

    elif len(
        candidates
    ) == 1:
        status = "exact_unique"
        entity = candidates[0]

    else:
        status = "ambiguous"
        entity = None

    return {
        "version": (
            ENTITY_RESOLUTION_VERSION
        ),
        "status": status,
        "query": {
            "alias_text": (
                _clean(
                    alias_text
                )
            ),
            "normalized_alias": (
                normalized_alias
            ),
            "entity_type": (
                normalized_type
            ),
            "sport_key": (
                normalized_sport
            ),
        },
        "entity": entity,
        "candidates": candidates,
        "candidate_count": len(
            candidates
        ),
        "policy": {
            "exact_alias_only": True,
            "ambiguity_fails_closed": True,
            "no_fuzzy_guessing": True,
            "alias_resolution_is_candidate_only": True,
            "trusted_for_authority": False,
            "verified_binding_required_for_authority": True,
            "does_not_change_live_merit": True,
        },
    }

VERIFIED_ENTITY_IMPORT_VERSION = (
    "verified-entity-import-v1"
)


def import_verified_entity(
    *,
    entity_key: str,
    entity_type: str,
    canonical_name: str,
    sport_key: str = "",
    aliases=(),
    metadata: Optional[
        Dict[str, Any]
    ] = None,
    seen_at: Optional[str] = None,
    connection_factory=None,
) -> Dict[str, Any]:
    if connection_factory is None:
        raise ValueError(
            "Verified entity import requires "
            "database access."
        )

    validated_aliases = []

    for alias_spec in aliases or ():
        if (
            not isinstance(
                alias_spec,
                (tuple, list),
            )
            or len(alias_spec) != 2
        ):
            raise ValueError(
                "Verified entity aliases must "
                "contain alias text and alias type."
            )

        alias_text = _clean(
            alias_spec[0]
        )
        alias_type = _key(
            alias_spec[1]
        )

        if not normalize_entity_alias(
            alias_text
        ):
            raise ValueError(
                "Verified entity alias text is required."
            )

        if (
            alias_type
            not in ENTITY_ALIAS_TYPES
        ):
            raise ValueError(
                "Verified entity alias type is unsupported."
            )

        validated_aliases.append(
            (
                alias_text,
                alias_type,
            )
        )

    entity_result = (
        upsert_canonical_entity(
            entity_key=entity_key,
            entity_type=entity_type,
            canonical_name=canonical_name,
            sport_key=sport_key,
            metadata=metadata,
            seen_at=seen_at,
            connection_factory=connection_factory,
        )
    )

    entity = entity_result[
        "entity"
    ]

    alias_results = [
        record_entity_alias(
            entity_id=entity["id"],
            alias_text=canonical_name,
            alias_type="canonical_name",
            metadata=metadata,
            seen_at=seen_at,
            connection_factory=connection_factory,
        )
    ]

    for (
        alias_text,
        alias_type,
    ) in validated_aliases:
        alias_results.append(
            record_entity_alias(
                entity_id=entity["id"],
                alias_text=alias_text,
                alias_type=alias_type,
                metadata=metadata,
                seen_at=seen_at,
                connection_factory=connection_factory,
            )
        )

    return {
        "version": (
            VERIFIED_ENTITY_IMPORT_VERSION
        ),
        "entity": entity,
        "entity_created": (
            entity_result["created"]
        ),
        "aliases": [
            result["alias"]
            for result
            in alias_results
        ],
        "alias_count": len(
            alias_results
        ),
        "policy": {
            "verified_input_required": True,
            "canonical_name_alias_recorded": True,
            "explicit_aliases_only": True,
            "no_alias_inference": True,
            "no_fuzzy_matching": True,
            "no_model_calls": True,
            "does_not_change_live_merit": True,
        },
    }


def import_verified_entities(
    *,
    entities,
    metadata: Optional[
        Dict[str, Any]
    ] = None,
    seen_at: Optional[str] = None,
    connection_factory=None,
) -> Dict[str, Any]:
    if connection_factory is None:
        raise ValueError(
            "Verified entity import requires "
            "database access."
        )

    imports = []

    for entity in entities or ():
        if not isinstance(
            entity,
            dict,
        ):
            raise ValueError(
                "Verified entity entries must "
                "be dictionaries."
            )

        imports.append(
            import_verified_entity(
                entity_key=entity.get(
                    "entity_key",
                    "",
                ),
                entity_type=entity.get(
                    "entity_type",
                    "",
                ),
                canonical_name=entity.get(
                    "canonical_name",
                    "",
                ),
                sport_key=entity.get(
                    "sport_key",
                    "",
                ),
                aliases=entity.get(
                    "aliases",
                    (),
                ),
                metadata=metadata,
                seen_at=seen_at,
                connection_factory=connection_factory,
            )
        )

    return {
        "version": (
            VERIFIED_ENTITY_IMPORT_VERSION
        ),
        "imports": imports,
        "entity_count": len(
            imports
        ),
        "policy": {
            "verified_input_required": True,
            "explicit_catalog_entries_only": True,
            "runtime_entity_creation": False,
            "no_fuzzy_matching": True,
            "no_model_calls": True,
            "does_not_change_live_merit": True,
        },
    }

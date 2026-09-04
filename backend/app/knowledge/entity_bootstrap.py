from typing import Any, Dict

from app.knowledge.entities import (
    import_verified_entities,
)


ENTITY_BOOTSTRAP_VERSION = "entity-bootstrap-v1"


VERIFIED_ENTITY_BOOTSTRAP = (
    {
        "entity_key": "football|club|manchester-united",
        "entity_type": "club",
        "canonical_name": "Manchester United",
        "sport_key": "football",
        "aliases": (
            ("Man Utd", "common_name"),
            ("Manchester Utd", "common_name"),
            ("MUFC", "abbreviation"),
        ),
    },
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
        "entity_key": "f1|team|mclaren",
        "entity_type": "team",
        "canonical_name": "McLaren Racing",
        "sport_key": "f1",
        "aliases": (
            ("McLaren F1", "common_name"),
        ),
    },
    {
        "entity_key": "cricket|team|mumbai-indians",
        "entity_type": "team",
        "canonical_name": "Mumbai Indians",
        "sport_key": "cricket",
        "aliases": (),
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


def bootstrap_verified_entities(
    *,
    connection_factory,
) -> Dict[str, Any]:
    if connection_factory is None:
        raise ValueError(
            "Verified entity bootstrap requires database access."
        )

    result = import_verified_entities(
        entities=VERIFIED_ENTITY_BOOTSTRAP,
        metadata={
            "catalog": ENTITY_BOOTSTRAP_VERSION,
            "verified_catalog_entry": True,
        },
        connection_factory=connection_factory,
    )

    return {
        "version": ENTITY_BOOTSTRAP_VERSION,
        "entities": [
            imported["entity"]
            for imported in result["imports"]
        ],
        "entity_count": result["entity_count"],
        "policy": {
            "verified_static_catalog_only": True,
            "uses_verified_import_path": True,
            "runtime_entity_creation": False,
            "fuzzy_matching": False,
            "model_calls": False,
        },
    }
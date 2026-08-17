from __future__ import annotations


MULTIMODAL_GOLDEN_SET_VERSION = "multimodal-golden-set-v1"
MULTIMODAL_GOLDEN_DATASET_ID = "sportabase-multimodal-golden-v1"

CORPUS_POLICY = {
    "historical_scenario_derived": True,
    "capture_text_is_original_paraphrase": True,
    "publisher_verbatim_text_included": False,
    "network_fetch_required": False,
    "gemini_required_for_default_run": False,
    "golden_labels_are_evaluation_labels_not_truth_authority": True,
    "live_merit_effect_allowed": False,
}

DEFAULT_LIMITS = {
    "scan_limit": 100,
    "max_candidates": 12,
}

HARD_THRESHOLDS = {
    "forbidden_shortlist_leakage": 0.0,
    "safety_policy_pass_rate": 1.0,
}

QUALITY_TARGETS = {
    "case_pass_rate": 1.0,
    "required_shortlist_recall": 1.0,
    "selection_status_accuracy": 1.0,
    "subject_partition_accuracy": 1.0,
    "required_member_recall": 1.0,
    "required_rejected_recall": 1.0,
}

# These are frozen, original paraphrases of historical sports scenarios.
# They deliberately do not copy publisher prose. The corpus evaluates routing,
# entity partitioning, negative leakage and safety boundaries; it is not a
# truth database and its labels do not establish source authority.
STANDARD_CASES = [
    {
        "case_id": "football_mbappe_real_madrid_2024",
        "sport": "football",
        "entity": ("golden_entity_01", "football|player|kylian-mbappe", "player", "Kylian Mbappe", ["Mbappe"]),
        "anchor_platform": "web",
        "related_platforms": ["x", "reddit"],
        "anchor": "Kylian Mbappe joined Real Madrid in 2024 after leaving Paris Saint-Germain.",
        "related": [
            "Kylian Mbappe completed his move to Real Madrid and was presented as a new signing.",
            "Real Madrid confirmed Kylian Mbappe as a new player for the club.",
        ],
        "hard_negative": "Kylian Mbappe discussed a minor training issue unrelated to his transfer announcement.",
        "unrelated": "A basketball playoff game went to overtime after a late three-pointer.",
    },
    {
        "case_id": "football_bellingham_real_madrid_2023",
        "sport": "football",
        "entity": ("golden_entity_02", "football|player|jude-bellingham", "player", "Jude Bellingham", ["Bellingham"]),
        "anchor_platform": "x",
        "related_platforms": ["web", "youtube"],
        "anchor": "Jude Bellingham completed his move to Real Madrid in 2023.",
        "related": [
            "Jude Bellingham signed for Real Madrid after his transfer from Borussia Dortmund.",
            "Real Madrid presented Jude Bellingham as a new midfielder.",
        ],
        "hard_negative": "Jude Bellingham later scored in a league match, a different claim from his transfer.",
        "unrelated": "A tennis player advanced after winning in straight sets.",
    },
    {
        "case_id": "football_messi_inter_miami_2023",
        "sport": "football",
        "entity": ("golden_entity_03", "football|player|lionel-messi", "player", "Lionel Messi", ["Messi"]),
        "anchor_platform": "web",
        "related_platforms": ["instagram", "reddit"],
        "anchor": "Lionel Messi joined Inter Miami in 2023.",
        "related": [
            "Lionel Messi was announced as an Inter Miami player after leaving European club football.",
            "Inter Miami introduced Lionel Messi to supporters.",
        ],
        "hard_negative": "Lionel Messi won an individual award months later, which is not the transfer claim.",
        "unrelated": "A Formula One team changed its front wing specification.",
    },
    {
        "case_id": "football_klopp_liverpool_exit_2024",
        "sport": "football",
        "entity": ("golden_entity_04", "football|person|jurgen-klopp", "person", "Jurgen Klopp", ["Klopp"]),
        "anchor_platform": "x",
        "related_platforms": ["web", "facebook"],
        "anchor": "Jurgen Klopp announced he would leave Liverpool at the end of the 2023-24 season.",
        "related": [
            "Liverpool confirmed Jurgen Klopp would step down after the season.",
            "Jurgen Klopp explained his decision to leave Liverpool after nearly nine years.",
        ],
        "hard_negative": "Jurgen Klopp spoke about a match injury update, a separate claim from his departure.",
        "unrelated": "A cricket captain chose to bat first after winning the toss.",
    },
    {
        "case_id": "football_arne_slot_liverpool_2024",
        "sport": "football",
        "entity": ("golden_entity_05", "football|person|arne-slot", "person", "Arne Slot", ["Slot"]),
        "anchor_platform": "web",
        "related_platforms": ["youtube", "x"],
        "anchor": "Arne Slot was appointed Liverpool head coach in 2024.",
        "related": [
            "Liverpool announced Arne Slot as the club's incoming head coach.",
            "Arne Slot confirmed he would take over at Liverpool after leaving Feyenoord.",
        ],
        "hard_negative": "Arne Slot later discussed preseason tactics, not the appointment itself.",
        "unrelated": "A cycling stage finished with a sprint victory.",
    },
    {
        "case_id": "football_kroos_retirement_2024",
        "sport": "football",
        "entity": ("golden_entity_06", "football|player|toni-kroos", "player", "Toni Kroos", ["Kroos"]),
        "anchor_platform": "instagram",
        "related_platforms": ["web", "x"],
        "anchor": "Toni Kroos announced he would retire from professional football after Euro 2024.",
        "related": [
            "Toni Kroos confirmed his playing career would end after the European Championship.",
            "Real Madrid acknowledged Toni Kroos's retirement announcement.",
        ],
        "hard_negative": "Toni Kroos was named in a match lineup, a different claim from retirement.",
        "unrelated": "A baseball pitcher recorded ten strikeouts.",
    },
    {
        "case_id": "football_xabi_alonso_stays_2024",
        "sport": "football",
        "entity": ("golden_entity_07", "football|person|xabi-alonso", "person", "Xabi Alonso", ["Alonso"]),
        "anchor_platform": "web",
        "related_platforms": ["x", "tiktok"],
        "anchor": "Xabi Alonso announced in 2024 that he would remain Bayer Leverkusen coach.",
        "related": [
            "Xabi Alonso said he would stay with Bayer Leverkusen for the following season.",
            "Bayer Leverkusen confirmed Xabi Alonso would continue as coach.",
        ],
        "hard_negative": "Xabi Alonso later discussed a cup final, a separate claim from staying at the club.",
        "unrelated": "A golf tournament was delayed by heavy rain.",
    },
    {
        "case_id": "football_man_city_ucl_2023",
        "sport": "football",
        "entity": ("golden_entity_08", "football|club|manchester-city", "club", "Manchester City", ["Man City"]),
        "anchor_platform": "reddit",
        "related_platforms": ["web", "x"],
        "anchor": "Manchester City won the 2023 UEFA Champions League final.",
        "related": [
            "Manchester City became European champions after winning the 2023 final.",
            "Manchester City lifted the Champions League trophy to complete a historic season.",
        ],
        "hard_negative": "Manchester City announced a player injury later, unrelated to the final result.",
        "unrelated": "A motorsport driver received a grid penalty.",
    },
    {
        "case_id": "f1_hamilton_ferrari_2024",
        "sport": "f1",
        "entity": ("golden_entity_09", "f1|person|lewis-hamilton", "person", "Lewis Hamilton", ["Hamilton"]),
        "anchor_platform": "web",
        "related_platforms": ["x", "youtube"],
        "anchor": "Lewis Hamilton agreed to join Ferrari for the 2025 Formula One season.",
        "related": [
            "Ferrari announced Lewis Hamilton would drive for the team from 2025.",
            "Lewis Hamilton's move to Ferrari for 2025 was confirmed after his Mercedes departure.",
        ],
        "hard_negative": "Lewis Hamilton qualified on the front row at a later race, a separate claim from the move.",
        "unrelated": "A football club signed a new goalkeeper.",
    },
    {
        "case_id": "f1_sainz_williams_2024",
        "sport": "f1",
        "entity": ("golden_entity_10", "f1|person|carlos-sainz", "person", "Carlos Sainz", ["Sainz"]),
        "anchor_platform": "x",
        "related_platforms": ["web", "instagram"],
        "anchor": "Carlos Sainz agreed to join Williams for the 2025 Formula One season.",
        "related": [
            "Williams announced Carlos Sainz as a driver for 2025.",
            "Carlos Sainz confirmed his move to Williams on a multi-year agreement.",
        ],
        "hard_negative": "Carlos Sainz later received a race penalty, unrelated to his Williams move.",
        "unrelated": "A basketball team traded a veteran center.",
    },
    {
        "case_id": "f1_hulkenberg_sauber_2024",
        "sport": "f1",
        "entity": ("golden_entity_11", "f1|person|nico-hulkenberg", "person", "Nico Hulkenberg", ["Hulkenberg"]),
        "anchor_platform": "web",
        "related_platforms": ["reddit", "x"],
        "anchor": "Nico Hulkenberg agreed to join Sauber for the 2025 Formula One season.",
        "related": [
            "Sauber announced Nico Hulkenberg would race for the team from 2025.",
            "Nico Hulkenberg confirmed his future move to Sauber ahead of the Audi era.",
        ],
        "hard_negative": "Nico Hulkenberg later discussed qualifying pace, a different claim from his move.",
        "unrelated": "A football manager received a touchline suspension.",
    },
    {
        "case_id": "f1_alonso_aston_extension_2024",
        "sport": "f1",
        "entity": ("golden_entity_12", "f1|person|fernando-alonso", "person", "Fernando Alonso", ["Alonso"]),
        "anchor_platform": "youtube",
        "related_platforms": ["web", "x"],
        "anchor": "Fernando Alonso extended his Aston Martin contract through the 2026 season.",
        "related": [
            "Aston Martin confirmed Fernando Alonso would remain with the team through 2026.",
            "Fernando Alonso announced a new multi-year agreement with Aston Martin.",
        ],
        "hard_negative": "Fernando Alonso later retired from a race with a technical problem, a separate claim.",
        "unrelated": "A hockey team won after a shootout.",
    },
    {
        "case_id": "f1_perez_red_bull_extension_2024",
        "sport": "f1",
        "entity": ("golden_entity_13", "f1|person|sergio-perez", "person", "Sergio Perez", ["Perez"]),
        "anchor_platform": "web",
        "related_platforms": ["facebook", "x"],
        "anchor": "Sergio Perez signed a Red Bull contract extension announced in 2024.",
        "related": [
            "Red Bull confirmed a new contract for Sergio Perez beyond the 2024 season.",
            "Sergio Perez said he had agreed fresh terms with Red Bull.",
        ],
        "hard_negative": "Sergio Perez later had a difficult qualifying session, unrelated to the contract announcement.",
        "unrelated": "A football federation revealed a tournament draw.",
    },
    {
        "case_id": "f1_leclerc_monaco_win_2024",
        "sport": "f1",
        "entity": ("golden_entity_14", "f1|person|charles-leclerc", "person", "Charles Leclerc", ["Leclerc"]),
        "anchor_platform": "x",
        "related_platforms": ["web", "tiktok"],
        "anchor": "Charles Leclerc won the 2024 Monaco Grand Prix.",
        "related": [
            "Charles Leclerc took victory at his home Monaco Grand Prix in 2024.",
            "Ferrari celebrated Charles Leclerc's Monaco Grand Prix win.",
        ],
        "hard_negative": "Charles Leclerc later received a practice-session warning, a separate claim.",
        "unrelated": "A rugby side changed its starting fly-half.",
    },
    {
        "case_id": "f1_verstappen_title_2023",
        "sport": "f1",
        "entity": ("golden_entity_15", "f1|person|max-verstappen", "person", "Max Verstappen", ["Verstappen"]),
        "anchor_platform": "web",
        "related_platforms": ["youtube", "reddit"],
        "anchor": "Max Verstappen secured the 2023 Formula One world championship.",
        "related": [
            "Max Verstappen clinched the 2023 drivers' title before the season ended.",
            "Red Bull celebrated Max Verstappen becoming 2023 world champion.",
        ],
        "hard_negative": "Max Verstappen later won another race, a separate claim from securing the title.",
        "unrelated": "A football club unveiled a new away kit.",
    },
    {
        "case_id": "f1_mclaren_constructors_2024",
        "sport": "f1",
        "entity": ("golden_entity_16", "f1|team|mclaren", "team", "McLaren", ["McLaren Racing"]),
        "anchor_platform": "instagram",
        "related_platforms": ["web", "x"],
        "anchor": "McLaren secured the 2024 Formula One constructors championship.",
        "related": [
            "McLaren won the 2024 constructors title after the final race.",
            "McLaren celebrated becoming Formula One constructors champions in 2024.",
        ],
        "hard_negative": "McLaren later announced a simulator programme update, unrelated to the title result.",
        "unrelated": "A tennis tournament changed its court schedule.",
    },
]

SPECIAL_CASES = [
    {
        "kind": "multilingual",
        "case_id": "multilingual_hamilton_ferrari",
        "sport": "f1",
        "entity": ("golden_entity_17", "f1|person|lewis-hamilton", "person", "Lewis Hamilton", ["Hamilton"]),
        "anchor": "Lewis Hamilton agreed to join Ferrari for the 2025 Formula One season.",
        "related": [
            "Lewis Hamilton se unirá a Ferrari para la temporada 2025 de Fórmula 1.",
            "Lewis Hamilton rejoindra Ferrari pour la saison 2025 de Formule 1.",
        ],
        "hard_negative": "Lewis Hamilton signe un meilleur tour en essais, information distincte du transfert.",
        "unrelated": "Arsenal prepared for a weekend league fixture with a changed defensive lineup.",
    },
    {
        "kind": "identical_content",
        "case_id": "dependency_like_identical_content",
        "sport": "f1",
        "entity": ("golden_entity_18", "f1|person|carlos-sainz", "person", "Carlos Sainz", ["Sainz"]),
        "anchor": "Carlos Sainz agreed to join Williams for the 2025 Formula One season.",
        "related": "Carlos Sainz confirmed a move to Williams beginning with the 2025 Formula One season.",
        "hard_negative": "Carlos Sainz reported a tyre issue during practice at a later event.",
        "unrelated": "A cricket opener reached a century before the tea interval.",
    },
    {
        "kind": "ambiguous_subject",
        "case_id": "ambiguous_liverpool_transition",
        "sport": "football",
        "entities": [
            ("golden_entity_19a", "football|person|jurgen-klopp", "person", "Jurgen Klopp", ["Klopp"]),
            ("golden_entity_19b", "football|person|arne-slot", "person", "Arne Slot", ["Slot"]),
        ],
        "anchor": "Liverpool moved from Jurgen Klopp to Arne Slot in its 2024 coaching transition.",
        "candidate_a": "Jurgen Klopp confirmed he would leave Liverpool after the season.",
        "candidate_b": "Arne Slot was announced as Liverpool head coach for the next season.",
        "unrelated": "A Formula One car completed a tyre test at a private circuit.",
    },
    {
        "kind": "multiple_shared_entities",
        "case_id": "multiple_shared_entities_rejected",
        "sport": "f1",
        "entities": [
            ("golden_entity_20a", "f1|person|lewis-hamilton", "person", "Lewis Hamilton", ["Hamilton"]),
            ("golden_entity_20b", "f1|team|ferrari", "team", "Ferrari", []),
        ],
        "anchor": "Lewis Hamilton will join Ferrari for the 2025 Formula One season.",
        "double_shared": "Lewis Hamilton and Ferrari confirmed their 2025 partnership.",
        "single_shared": "Lewis Hamilton confirmed a team change beginning in the 2025 season.",
        "unrelated": "A football striker scored twice in a domestic cup match.",
    },
    {
        "kind": "no_signal",
        "case_id": "no_signal_fail_closed",
        "sport": "f1",
        "entity": ("golden_entity_21", "f1|person|lewis-hamilton", "person", "Lewis Hamilton", ["Hamilton"]),
        "anchor": "Lewis Hamilton agreed to join Ferrari for the 2025 Formula One season.",
        "unrelated": [
            "Arsenal prepared a defensive shape for a weekend league fixture.",
            "A cricket bowler took five wickets before lunch at the test match.",
        ],
    },
]


def frozen_case_specs():
    return [
        *STANDARD_CASES,
        *SPECIAL_CASES,
    ]

import ast
import importlib
import sys
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


from app import main


MAIN_PATH = (
    BACKEND_DIR
    / "app"
    / "main.py"
)


SERVICE_MODULES = (
    "app.services.content_resolution",
    "app.services.analysis_history",
    "app.services.analysis_cache",
    "app.services.gemini_runtime",
    "app.services.article_rules",
    "app.services.video_support",
    "app.services.video_analysis",
    "app.services.article_analysis",
    "app.services.analysis_handlers",
    "app.services.legacy_handlers",
    "app.services.intelligence_facade",
)


OPERATIONS_MODULES = (
    "app.operations.usage",
)


COMPATIBILITY_MODULES = (
    "app.services.usage_reporting",
)


ROUTE_MODULES = (
    "app.routes.product_api",
    "app.routes.usage_admin",
    "app.routes.multimodal_admin",
)


APPLICATION_MODULES = (
    "app.application.config",
    "app.application.composition",
)


SHALLOW_ROUTE_NAMES = (
    "health",
    "admin_usage_summary",
    "ingest",
    "stories",
    "resolve_content",
    "analyze_video",
    "analyze",
)


DELEGATED_FUNCTIONS = (
    "analysis_content_hash",
    "source_domain_for_url",
    "source_key_for_url",
    "source_id_for_url",
    "upsert_intelligence_source",
    "upsert_intelligence_story",
    "upsert_intelligence_claim",
    "record_claim_link",
    "link_media_item_to_story",
    "upsert_intelligence_reporter",
    "record_source_observation",
    "record_reporter_observation",
    "record_evidence",
    "record_evidence_link",
    "record_observation_dependency",
    "record_observation_independence_assertion",
    "load_evidence_context_for_media_item",
    "load_evidence_analysis_state_for_media_item",
    "media_item_id_for_url",
    "upsert_media_item",
    "find_analysis_snapshot",
    "persist_analysis_snapshot",
    "record_user_history",
    "make_analysis_cache_key",
    "get_cached_analysis",
    "set_cached_analysis",
    "reserve_gemini_call",
    "generate_gemini_content",
    "record_analysis_cache_hit",
    "usage_derived_metrics",
    "usage_mode_metrics",
    "gemini_candidate_semantics",
    "gemini_candidate_collection_semantics",
    "gemini_tldr",
    "gemini_article_single_pass",
    "ai_detect_article_type",
    "run_article_ai_strategy",
    "ai_video_claim_readout",
    "resolve_article_content",
)


class MainDecompositionContractTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls):
        cls.source = MAIN_PATH.read_text(
            encoding="utf-8"
        )

        cls.tree = ast.parse(
            cls.source
        )

        cls.functions = {
            node.name: node
            for node in cls.tree.body
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
        }

    def test_application_bootstrap_modules_import(
        self,
    ):
        for module_name in APPLICATION_MODULES:
            with self.subTest(
                module=module_name
            ):
                module = importlib.import_module(
                    module_name
                )

                self.assertIsNotNone(
                    module
                )

    def test_operations_modules_import(
        self,
    ):
        for module_name in OPERATIONS_MODULES:
            with self.subTest(
                module=module_name
            ):
                module = importlib.import_module(
                    module_name
                )

                self.assertIsNotNone(
                    module
                )

    def test_historical_compatibility_modules_import(
        self,
    ):
        for module_name in COMPATIBILITY_MODULES:
            with self.subTest(
                module=module_name
            ):
                module = importlib.import_module(
                    module_name
                )

                self.assertIsNotNone(
                    module
                )

    def test_main_stays_within_decomposition_budget(
        self,
    ):
        line_count = len(
            self.source.splitlines()
        )

        self.assertLessEqual(
            line_count,
            2200,
            (
                "main.py exceeded the decomposition "
                "budget. New business logic should "
                "live in services/routes rather than "
                "growing main.py again."
            ),
        )

    def test_main_contains_no_direct_sql_execution(
        self,
    ):
        forbidden = (
            ".execute(",
            "INSERT INTO ",
            "UPDATE ",
            "DELETE FROM ",
            "SELECT *",
        )

        for marker in forbidden:
            with self.subTest(
                marker=marker
            ):
                self.assertNotIn(
                    marker,
                    self.source,
                )

    def test_main_contains_no_direct_remote_fetch_logic(
        self,
    ):
        forbidden = (
            "requests.get(",
            "requests.post(",
            "requests.request(",
            "feedparser.parse(",
            "BeautifulSoup(",
        )

        for marker in forbidden:
            with self.subTest(
                marker=marker
            ):
                self.assertNotIn(
                    marker,
                    self.source,
                )

    def test_extracted_service_modules_import(
        self,
    ):
        for module_name in SERVICE_MODULES:
            with self.subTest(
                module=module_name
            ):
                module = (
                    importlib.import_module(
                        module_name
                    )
                )

                self.assertIsNotNone(
                    module
                )

    def test_extracted_route_modules_import(
        self,
    ):
        for module_name in ROUTE_MODULES:
            with self.subTest(
                module=module_name
            ):
                module = importlib.import_module(
                    module_name
                )

                self.assertIsNotNone(
                    module
                )

    def test_main_owns_no_http_route_decorators(
        self,
    ):
        forbidden = (
            "@app.get(",
            "@app.post(",
            "@app.put(",
            "@app.patch(",
            "@app.delete(",
        )

        for marker in forbidden:
            with self.subTest(
                marker=marker
            ):
                self.assertNotIn(
                    marker,
                    self.source,
                )

    def test_main_delegates_application_bootstrap(
        self,
    ):
        forbidden = (
            "FastAPI(",
            "CORSMiddleware",
            ".include_router(",
            "register_browser_capture_automation_lifecycle(",
            "load_dotenv(",
            "SPORTABASE_MAX_ANALYZE_CHARS",
        )

        for marker in forbidden:
            with self.subTest(
                marker=marker
            ):
                self.assertNotIn(
                    marker,
                    self.source,
                )

        required = (
            "create_application()",
            "register_startup_handler(",
            "compose_application(",
        )

        for marker in required:
            with self.subTest(
                marker=marker
            ):
                self.assertIn(
                    marker,
                    self.source,
                )

    def test_key_routes_remain_shallow(
        self,
    ):
        for name in SHALLOW_ROUTE_NAMES:
            with self.subTest(
                function=name
            ):
                self.assertIn(
                    name,
                    self.functions,
                )

                node = self.functions[
                    name
                ]

                self.assertLessEqual(
                    len(node.body),
                    2,
                    (
                        f"{name} accumulated route "
                        "business logic in main.py."
                    ),
                )

    def test_extracted_functions_remain_delegators(
        self,
    ):
        for name in DELEGATED_FUNCTIONS:
            with self.subTest(
                function=name
            ):
                self.assertIn(
                    name,
                    self.functions,
                )

                node = self.functions[
                    name
                ]

                self.assertEqual(
                    len(node.body),
                    1,
                    (
                        f"{name} is no longer a thin "
                        "compatibility delegator."
                    ),
                )

                self.assertIsInstance(
                    node.body[0],
                    ast.Return,
                    (
                        f"{name} should delegate through "
                        "a return expression."
                    ),
                )

    def test_no_large_top_level_function_body_returns(
        self,
    ):
        offenders = []

        for name, node in (
            self.functions.items()
        ):
            statement_count = len(
                node.body
            )

            if statement_count > 8:
                offenders.append(
                    (
                        name,
                        statement_count,
                    )
                )

        self.assertEqual(
            offenders,
            [],
            (
                "Large implementation logic returned "
                "to main.py: "
                + repr(
                    offenders
                )
            ),
        )

    def test_database_initialization_is_deferred_to_startup(
        self,
    ):
        startup_handlers = list(
            getattr(
                main.app.state,
                "_sportabase_startup_handlers",
                (),
            )
        )

        self.assertIn(
            main.init_db,
            startup_handlers,
            (
                "Database schema initialization must "
                "remain registered for application startup."
            ),
        )

        top_level_init_calls = []

        for node in self.tree.body:
            if not isinstance(
                node,
                ast.Expr,
            ):
                continue

            value = node.value

            if not isinstance(
                value,
                ast.Call,
            ):
                continue

            function = value.func

            if (
                isinstance(
                    function,
                    ast.Name,
                )
                and function.id
                == "init_db"
            ):
                top_level_init_calls.append(
                    node.lineno
                )

        self.assertEqual(
            top_level_init_calls,
            [],
            (
                "Importing app.main must not initialize "
                "or mutate the persistent database."
            ),
        )

    def test_public_api_contract_is_present(
        self,
    ):
        paths = (
            main.app
            .openapi()[
                "paths"
            ]
        )

        required_paths = {
            "/health",
            "/ingest",
            "/stories",
            "/admin/usage/summary",
            "/resolve-content",
            "/analyze/video",
            "/analyze",
        }

        self.assertTrue(
            required_paths.issubset(
                set(
                    paths
                )
            )
        )

        self.assertEqual(
            main.app.version,
            "0.3.0",
        )


if __name__ == "__main__":
    unittest.main()

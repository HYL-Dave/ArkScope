"""Owners for the source-only maintenance census, not product behavior."""

import importlib
import importlib.util

import pytest


def inventory():
    assert importlib.util.find_spec("tests.repository_inventory") is not None, (
        "repeatable repository inventory owner missing"
    )
    return importlib.import_module("tests.repository_inventory")


def test_relative_imports_and_package_reexports_have_real_edges():
    report = inventory().python_inventory({
        "src/__init__.py": "",
        "src/pkg/__init__.py": "from . import child\n",
        "src/pkg/child.py": "from .. import shared\n",
        "src/shared.py": "value = 1\n",
        "src/main.py": "from src.pkg import child\n",
    })
    rows = {row["module"]: row for row in report["modules"]}
    assert "src.pkg" in rows["src.pkg.child"]["runtime_importers"]
    assert "src.main" in rows["src.pkg.child"]["runtime_importers"]
    assert "src.pkg.child" in rows["src.shared"]["runtime_importers"]


def test_test_only_module_is_distinct_from_orphan_and_cli():
    report = inventory().python_inventory({
        "src/only_test.py": "value = 1\n",
        "src/orphan.py": "value = 1\n",
        "src/operator.py": 'if __name__ == "__main__":\n    print("operator")\n',
        "src/api/__main__.py": "pass\n",
        "tests/test_one.py": "from src.only_test import value\n",
    })
    rows = {row["module"]: row for row in report["modules"]}
    assert rows["src.only_test"]["reference_state"] == "test_only"
    assert rows["src.orphan"]["reference_state"] == "no_inbound_reference"
    assert rows["src.operator"]["entrypoint_kind"] == "main_guard"
    assert rows["src.api.__main__"]["entrypoint_kind"] == "module_main"
    assert all(row["deletion_authorized"] is False for row in rows.values())


def test_literal_dynamic_import_and_adapter_string_are_not_orphans():
    report = inventory().python_inventory({
        "src/runner.py": 'from importlib import import_module as load\nload("src.plugin")\nadapter = ("src.adapter", "run")\nload(chosen)\n',
        "src/plugin.py": "pass\n",
        "src/adapter.py": "pass\n",
    })
    rows = {row["module"]: row for row in report["modules"]}
    assert rows["src.plugin"]["runtime_importers"] == ["src.runner"]
    assert rows["src.adapter"]["string_referrers"] == ["src.runner"]
    assert any(site["kind"] == "dynamic_import" for site in report["unresolved"])


def test_parse_error_is_coverage_failure_not_clean_module():
    report = inventory().python_inventory({"src/broken.py": "def broken(:\n"})
    assert report["coverage"]["python_files"] == 1
    assert report["coverage"]["parsed_python_files"] == 0
    assert report["parse_errors"][0]["path"] == "src/broken.py"


def test_settings_literal_snapshot_and_dynamic_access_remain_distinct():
    report = inventory().python_inventory({
        "src/config.py": '''
KEY = "budget"
store.set_setting(KEY, "42")
store.get_settings_snapshot((KEY, "enabled"))
store.set_setting("orphan.setting", "value")
store.get_setting(f"schedule.{name}.enabled")
''',
    })
    settings = {row["key"]: row for row in report["settings"]["keys"]}
    assert settings["budget"]["reads"] and settings["budget"]["writes"]
    assert settings["orphan.setting"]["state"] == "no_literal_reader_observed"
    assert report["settings"]["dynamic_accesses"]
    assert settings["orphan.setting"]["deletion_authorized"] is False


def test_transitive_calendar_dependency_is_not_unused():
    report = inventory().dependency_inventory(
        "exchange-calendars==4.13.2\nkorean-lunar-calendar==0.4.0\n",
        [{"name": "exchange_calendars", "path": "src/calendar.py", "line": 1}],
        {"packages": {"exchange_calendars": ["exchange-calendars"]},
         "distributions": {
             "exchange-calendars": {"version": "4.13.2", "requires": ["korean_lunar_calendar>=0.3.1"]},
             "korean-lunar-calendar": {"version": "0.4.0", "requires": []},
         }},
    )
    rows = {row["name"]: row for row in report["requirements"]}
    assert rows["exchange-calendars"]["state"] == "direct_import"
    assert rows["korean-lunar-calendar"]["state"] == "transitive_requirement"
    assert rows["korean-lunar-calendar"]["required_by"] == ["exchange-calendars"]


def test_missing_distribution_metadata_is_unknown_not_unused():
    report = inventory().dependency_inventory("missing-package==1\n", [],
        {"packages": {}, "distributions": {}})
    assert report["requirements"][0]["state"] == "metadata_unavailable"


def test_http_routes_keep_method_prefix_and_mount_uncertainty():
    report = inventory().python_inventory({
        "src/api/routes/example.py": '''
router = APIRouter(prefix="/items")
@router.get("/{ticker}")
def read(ticker): pass
@router.post("/refresh")
def refresh(): pass
''',
    })
    assert {(row["method"], row["path_template"]) for row in report["routes"]} == {
        ("GET", "/items/{ticker}"), ("POST", "/items/refresh")}
    assert all(row["mount_resolution"] == "router_local" for row in report["routes"])


def test_sqlite_parser_accounts_for_select_star_and_trigger_reads():
    report = inventory().sql_inventory([
        {"path": "src/schema.py", "line": 1, "text": "CREATE TABLE facts(id INTEGER, amount TEXT); CREATE TABLE receipts(id INTEGER);", "dynamic": False},
        {"path": "src/read.py", "line": 2, "text": "SELECT * FROM facts WHERE id=?", "dynamic": False},
        {"path": "src/trigger.py", "line": 3, "text": "CREATE TRIGGER guard BEFORE INSERT ON receipts BEGIN SELECT id FROM facts; END;", "dynamic": False},
    ])
    tables = {row["table"]: row for row in report["tables"]}
    assert set(tables["facts"]["read_columns"]) == {"id", "amount"}
    assert tables["facts"]["state"] == "reader_observed"
    assert report["triggers"]


def test_dynamic_sql_and_unknown_tables_are_explicit_gaps():
    report = inventory().sql_inventory([
        {"path": "src/store.py", "line": 1, "text": "SELECT * FROM {table}", "dynamic": True},
        {"path": "src/read.py", "line": 2, "text": "SELECT * FROM undefined", "dynamic": False},
    ])
    assert {row["kind"] for row in report["unresolved"]} >= {"dynamic_sql", "sql_prepare_failed"}


def test_source_inventory_excludes_private_and_generated_content():
    classify = inventory().classify_path
    assert classify("src/audit/operator.py") == "python"
    assert classify("apps/arkscope-desktop/main.js") == "frontend"
    assert classify("config/.env") == "excluded_private"
    assert classify("data/profile_state.db") == "excluded_private"
    assert classify("node_modules/pkg/index.js") == "excluded_dependency"
    assert classify("docs/superpowers/evidence/old/fixture.py") == "excluded_evidence"


def test_new_candidates_and_new_uncertainty_are_reported_not_hidden():
    before = {"candidates": [{"id": "python:existing"}], "uncertainties": []}
    after = {"candidates": [{"id": "python:existing"}, {"id": "python:new"}],
             "uncertainties": [{"id": "python:unparsed"}]}
    delta = inventory().compare_reports(before, after)
    assert delta["new_candidates"] == ["python:new"]
    assert delta["new_uncertainties"] == ["python:unparsed"]
    assert delta["review_required"] is True


def test_tracked_symlink_is_not_followed_outside_source_tree(tmp_path):
    outside = tmp_path / "private"
    outside.write_text("do not read")
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "link.py").symlink_to(outside)
    files, manifest = inventory().read_sources(root, ["src/link.py"])
    assert files == {}
    assert manifest[0]["status"] == "symlink_not_read"


def test_identical_inventory_input_is_deterministic():
    files = {"src/b.py": "pass\n", "src/a.py": "from . import b\n"}
    assert inventory().python_inventory(files) == inventory().python_inventory(dict(reversed(list(files.items()))))


def test_local_shadowing_cannot_fabricate_a_literal_settings_reader():
    report = inventory().python_inventory({"src/config.py": '''
KEY = "global.setting"
store.set_setting(KEY, "yes")
def read(KEY):
    return store.get_setting(KEY)
'''})
    row = next(row for row in report["settings"]["keys"] if row["key"] == "global.setting")
    assert row["reads"] == []
    assert report["settings"]["dynamic_accesses"]


def test_sql_sinks_with_unresolved_queries_or_leading_comments_are_counted():
    report = inventory().python_inventory({"src/store.py": '''
SCHEMA = "-- catalog\\nCREATE TABLE items(id INTEGER);"
conn.executescript(SCHEMA)
def read(query):
    conn.execute(query)
'''})
    assert report["sql_sink_coverage"]["calls"] == 2
    assert any("CREATE TABLE items" in row["text"] for row in report["sql_sites"])
    assert any(row["dynamic"] for row in report["sql_sites"])


def test_test_only_dynamic_import_is_classified_as_test_only():
    report = inventory().python_inventory({
        "src/operator.py": "pass\n",
        "tests/test_operator.py": 'import importlib\nimportlib.import_module("src.operator")\n',
    })
    row = next(row for row in report["modules"] if row["module"] == "src.operator")
    assert row["reference_state"] == "test_only"


def test_wheel_record_resolves_import_names_without_top_level_metadata():
    roots = inventory().package_roots([
        "openai-3.dist-info/METADATA", "openai/__init__.py", "openai/types/a.py",
        "typing_extensions.py", "pkg.data/scripts/tool", "../bin/tool",
    ])
    assert roots == {"openai", "typing_extensions"}


def test_sqlite_fts_shadow_tables_are_not_unused_table_candidates():
    sql = inventory().sql_inventory([{"path": "src/schema.py", "line": 1,
        "text": "CREATE VIRTUAL TABLE search USING fts5(body);", "dynamic": False}])
    shadow = [row for row in sql["tables"] if row.get("sqlite_table_kind") == "shadow"]
    assert shadow
    candidates = inventory().candidate_rows({"modules": [], "settings": {"keys": []}},
        {"requirements": []}, sql)
    assert not any(row["id"] == "table:" + table["table"] for row in candidates for table in shadow)


def test_module_callable_and_cross_language_launch_are_reference_witnesses():
    report = inventory().python_inventory({
        "src/api/__init__.py": "",
        "src/api/app.py": "pass\n",
        "src/api/__main__.py": 'uvicorn.run("src.api.app:create_app")\n',
        "apps/desktop/main.js": 'spawn(python, ["-m", "src.api"]);',
    })
    rows = {row["module"]: row for row in report["modules"]}
    assert rows["src.api.app"]["launch_witnesses"]
    assert rows["src.api.__main__"]["launch_witnesses"]
    assert rows["src.api.__main__"]["deletion_authorized"] is False


def test_report_aggregates_frontend_candidates_and_explicit_scan_gaps():
    frontend = {"i18n": {"keys": [{"namespace": "settings", "locale": "en", "key": "old",
                                  "status": "no-static-reference", "file": "en/settings.ts", "line": 1}]},
                "dependencies": {"candidates": []}, "css": {"selectors": []},
                "unresolved": [{"axis": "i18n", "reason": "dynamic-key", "file": "app.ts", "line": 2}],
                "coverage": {"parseErrors": []}}
    assert inventory().frontend_candidates(frontend)[0]["id"].startswith("i18n:")
    gaps = inventory().scan_uncertainties({}, {}, {}, frontend,
        [{"path": "src/a.py", "status": "decode_failed"}])
    assert {row["axis"] for row in gaps} >= {"i18n", "source"}
    assert inventory().scan_uncertainties({}, {}, {}, {"status": "not_run"}, [])


def test_i18n_candidate_ids_preserve_workspace_identity():
    keys = [{"locale": "en", "namespace": "common", "key": "title", "status": "unresolved",
             "file": path, "line": 1} for path in ("web/common.ts", "desktop/common.ts")]
    assert len({row["id"] for row in inventory().frontend_candidates({"i18n": {"keys": keys}})}) == 2


def test_http_template_matching_is_method_aware_not_a_deletion_verdict():
    routes = [{"method": "GET", "path_template": "/items/{ticker}"},
              {"method": "POST", "path_template": "/items/refresh"}]
    refs = [{"method": "GET", "url": "/items/${encodeURIComponent(ticker)}", "file": "api.ts"}]
    rows = inventory().http_inventory(routes, refs)["routes"]
    assert rows[0]["frontend_references"]
    assert not rows[1]["frontend_references"]
    assert rows[1]["deletion_authorized"] is False


def test_compare_reports_marks_narrowed_source_coverage_for_review():
    before = {"candidates": [], "uncertainties": [], "source_manifest": [
        {"path": "src/a.py", "status": "read"}]}
    after = {"candidates": [], "uncertainties": [], "source_manifest": [
        {"path": "src/a.py", "status": "excluded_private"}]}
    delta = inventory().compare_reports(before, after)
    assert delta["coverage_reductions"] == ["src/a.py"]
    assert delta["review_required"] is True


def test_comparison_owns_untracked_names_and_dependency_metadata_drift():
    before = {"untracked": {"paths": ["private/old.md"]}, "python_dependencies": {
        "requirements": [{"name": "example", "installed": {"version": "1"}}]}}
    after = {"untracked": {"paths": ["private/old.md", "private/new.md"]}, "python_dependencies": {
        "requirements": [{"name": "example", "installed": {"version": "2"}}]}}
    delta = inventory().compare_reports(before, after)
    assert delta["new_untracked_paths"] == ["private/new.md"]
    assert delta["dependency_metadata_changed"] == ["example"]
    assert delta["review_required"] is True


def test_create_only_compressed_report_is_repeatable_and_comparable(tmp_path):
    report = {"format": 1, "candidates": [], "uncertainties": []}
    a, b = tmp_path / "a.json.gz", tmp_path / "b.json.gz"
    inventory().write_report(a, report)
    inventory().write_report(b, report)
    assert a.read_bytes() == b.read_bytes()
    assert inventory().read_report(a) == report
    with pytest.raises(FileExistsError):
        inventory().write_report(a, report)


@pytest.mark.parametrize("name", ["src/user_profile.local.yml", "src/user_profile.local.yaml",
                                 "src/user_profile.local.json", ".env.development"])
def test_private_filename_variants_are_excluded_without_reading(name):
    assert inventory().classify_path(name) == "excluded_private"


def test_dependency_metadata_loss_is_a_review_required_uncertainty():
    before_deps = inventory().dependency_inventory("demo==1", [],
        {"packages": {}, "distributions": {"demo": {"version": "1", "requires": []}}})
    after_deps = inventory().dependency_inventory("demo==1", [], {"packages": {}, "distributions": {}})
    before = {"candidates": [], "uncertainties": inventory().scan_uncertainties({}, {}, before_deps, {}, [])}
    after = {"candidates": [], "uncertainties": inventory().scan_uncertainties({}, {}, after_deps, {}, [])}
    assert inventory().compare_reports(before, after)["review_required"] is True


def test_reassigned_or_conditional_constants_cannot_fabricate_readers():
    report = inventory().python_inventory({"src/config.py": '''
KEY = "old"
store.set_setting("old", "value")
KEY = choose()
store.get_setting(KEY)
QUERY = "SELECT * FROM pretend"
if changed:
    QUERY = unknown_query()
conn.execute(QUERY)
'''})
    old = next(row for row in report["settings"]["keys"] if row["key"] == "old")
    assert old["reads"] == []
    assert report["settings"]["dynamic_accesses"]
    assert report["sql_sink_coverage"]["dynamic"] == 1


def test_import_aliases_are_lexically_scoped():
    report = inventory().python_inventory({"src/loader.py": '''
import importlib
NAME = "src." + "plug"
def unused():
    import unrelated as importlib
importlib.import_module(NAME)
''', "src/plug.py": "pass"})
    assert ["src.loader", "src.plug"] in report["edges"]
    assert not any(row.get("name") == "unrelated.import_module" for row in report["external_imports"])
    local = inventory().python_inventory({"src/loader.py": '''
def local():
    from importlib import import_module as load
    load("src.plug")
''', "src/plug.py": "pass"})
    assert ["src.loader", "src.plug"] in local["edges"]


def test_column_specific_trigger_and_repeated_sql_keep_all_read_witnesses():
    report = inventory().sql_inventory([
        {"path": "src/schema.py", "line": 1, "text": "CREATE TABLE facts(secret TEXT); CREATE TABLE changes(a INT,z INT);", "dynamic": False},
        {"path": "src/trigger.py", "line": 2, "text": "CREATE TRIGGER guard AFTER UPDATE OF z ON changes BEGIN SELECT secret FROM facts; END;", "dynamic": False},
        {"path": "src/one.py", "line": 3, "text": "SELECT a FROM changes", "dynamic": False},
        {"path": "src/two.py", "line": 4, "text": "SELECT a FROM changes", "dynamic": False},
    ])
    rows = {row["table"]: row for row in report["tables"]}
    assert "secret" in rows["facts"]["read_columns"]
    assert {row["path"] for row in rows["changes"]["reads"]} >= {"src/one.py", "src/two.py"}


def test_cli_requires_review_instead_of_accepting_new_candidates(tmp_path, monkeypatch):
    module = inventory()
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src/one.py").write_text("pass\n")
    paths = ["src/one.py"]
    monkeypatch.setattr(module, "git_names", lambda _root, *args: [] if args else list(paths))
    monkeypatch.setattr(module, "installed_metadata", lambda: {"packages": {}, "distributions": {}})
    baseline, repeat, changed = (tmp_path / name for name in ("base.json", "same.json", "changed.json"))
    args = ["--root", str(root), "--skip-frontend"]
    assert module.main([*args, "--output", str(baseline)]) == 0
    assert module.main([*args, "--output", str(repeat), "--compare", str(baseline)]) == 0
    paths.append("src/new.py")
    (root / "src/new.py").write_text("pass\n")
    assert module.main([*args, "--output", str(changed), "--compare", str(baseline)]) == 2
    assert module.read_report(changed)["comparison"]["new_candidates"] == ["python:src.new"]

"""Isolated inverse probes: mutate loaded functions, never shared source files."""
import inspect
from contextlib import nullcontext
import textwrap
from pathlib import Path
import runpy
import sys

MODE = sys.argv.pop(1)
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parents[2]))
import pytest

original_main = pytest.main


def main(args):
    import src.sec_research.captures as captures
    import src.sec_research.capture_lock as locks
    if MODE == "quota":
        def admit_without_quota(self, size):
            if self.free_bytes(self.store.paths.capture_root) < size + captures.METADATA_SPACE_MARGIN:
                raise ValueError("storage_space_insufficient")
        captures.CaptureStore._admit = admit_without_quota
        selector = "tests/test_sec_research_captures.py::test_capacity_rejected_before_any_stage_write"
        print("Inverse: remove capture quota check, retain disk check")
    elif MODE == "replace":
        def clobber(directory, stage, sha):
            locks.os.rename(stage, sha, src_dir_fd=directory.children["staging"],
                            dst_dir_fd=directory.children["objects"])
        locks.CaptureDirectory.publish = clobber
        selector = "tests/test_sec_research_captures.py::test_publication_never_replaces_a_racing_destination"
        print("Inverse: replace create-only link publication with clobbering rename")
    elif MODE == "permission":
        import src.api.routes.sec_research as route
        source = inspect.getsource(route.refresh)
        source = source[source.index("def refresh"):].replace(
            '    require_db_write("sec_research_refresh", {"cik": cik})\n', "")
        exec(compile(source, "<inverse-permission>", "exec"), route.__dict__)
        # Rebind the already-declared route to the mutant endpoint for the fixture.
        route.router.routes[-1].endpoint = route.refresh
        route.router.routes[-1].dependant.call = route.refresh
        selector = "tests/test_sec_research_routes.py::test_permission_rejection_precedes_every_store_and_provider_construction"
        print("Inverse: remove permission boundary before refresh construction")
    elif MODE in {"shape", "float", "overwrite", "receipt-order"}:
        import src.sec_research.schema as schema
        import src.sec_research.store as store
        if MODE == "shape":
            schema.verify = lambda conn: None
            selector = "tests/test_sec_research_store.py::test_shape_mismatch_is_rejected_without_installing_anything"
        else:
            method = "latest_receipt" if MODE == "receipt-order" else "publish"
            source = inspect.getsource(getattr(store.Store, method))
            if MODE == "receipt-order":
                source = source.replace("ORDER BY receipt_id DESC", "ORDER BY recorded_at DESC, receipt_id DESC")
                selector = "tests/test_sec_research_store.py::test_latest_receipt_survives_clock_rollback_and_reopening"
            elif MODE == "float":
                target = '        normalized_rows = payload["filings" if kind == "catalog" else "facts"]\n'
                assert target in source
                source = source.replace(target, target + '        if kind == "facts":\n            for row in normalized_rows:\n                row["value"] = str(float(row["value"]))\n')
                selector = "tests/test_sec_research_store.py::test_exact_fact_text_and_amendments_reopen"
            else:
                schema._DDL = {name: definition for name, definition in schema._DDL.items()
                               if not (definition[0] == "trigger" and definition[1] in
                                       {"sec_research_filings", "sec_research_facts", "sec_research_snapshots"})}
                target = "        with self._write() as conn:\n"
                assert target in source
                source = source.replace(target, target + '''            conn.execute("DELETE FROM sec_research_filings WHERE cik=?", (cik,))
            conn.execute("DELETE FROM sec_research_facts WHERE cik=?", (cik,))
            conn.execute("DELETE FROM sec_research_snapshots WHERE cik=?", (cik,))
''')
                selector = "tests/test_sec_research_store.py::test_retained_snapshots_and_idempotent_publication"
            namespace = dict(store.__dict__)
            exec(compile(textwrap.dedent(source), "<inverse-store>", "exec"), namespace)
            setattr(store.Store, method, namespace[method])
        print("Inverse store:", MODE)
    elif MODE in {"preflight", "coverage", "checkpoint", "issuer"}:
        import src.sec_research.service as service
        if MODE in {"preflight", "checkpoint"}:
            source = inspect.getsource(service.ResearchService._refresh)
            if MODE == "preflight":
                source = source.replace("self.captures.preflight()", "None")
                selector = "tests/test_sec_research_service.py::test_preflight_blocks_first_and_each_later_request"
            else:
                old = "            checkpoint()\n\n        return self.store.latest_receipt(cik)"
                assert old in source
                source = source.replace(old, "            pass\n\n        return self.store.latest_receipt(cik)")
                selector = "tests/test_sec_research_service.py::test_real_crash_then_reopen_preserves_checkpoint"
            namespace = dict(service.__dict__)
            exec(compile(textwrap.dedent(source), "<inverse-service>", "exec"), namespace)
            service.ResearchService._refresh = namespace["_refresh"]
        elif MODE == "coverage":
            service._status = lambda completed, pending, gaps: "ok" if completed else "unavailable"
            selector = "tests/test_sec_research_service.py::test_unobserved_history_is_explicit_gap_even_after_noop_resume"
        else:
            service.issuer_refresh = lambda *a: nullcontext()
            selector = "tests/test_sec_research_service.py::test_same_issuer_overlap_is_rejected_without_overwriting_receipt"
        print("Inverse service:", MODE)
    else:
        raise ValueError(MODE)
    return original_main([*args, selector, "-q", "--junitxml=" + str(BASE / ("inverse-" + MODE + ".xml"))])


pytest.main = main
runpy.run_path(str(BASE / "offline_pytest.py"), run_name="__main__")

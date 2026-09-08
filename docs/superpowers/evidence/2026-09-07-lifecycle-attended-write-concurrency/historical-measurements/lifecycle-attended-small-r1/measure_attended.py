"""Offline attended adoption alongside a real worker in one temporary profile."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import resource
import socket
import sqlite3
import sys
import tempfile
from threading import Event, Thread, current_thread
import time
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--decoded-mib", type=int, required=True)
    parser.add_argument("--action", choices=("terminal_delisting", "symbol_continuation"), default="terminal_delisting")
    args = parser.parse_args()
    if args.output.exists() or not 1 <= args.decoded_mib <= 128:
        raise ValueError("new_output_and_bounded_measurement_required")
    sys.path.insert(0, str(args.repo.resolve()))
    from src import lifecycle_public_sources as sources
    from src import security_lifecycle_web_pipeline as pipeline
    from src.auth_drivers.lifecycle_web_models import WebCredential, ModelReply
    from src.lifecycle_web_controller import LifecycleWebController
    from src.lifecycle_web_review import prepare, confirm
    from src.lifecycle_web_schema import install_web_journal
    from src.lifecycle_web_store import LifecycleWebStore
    from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore, observation_fingerprint
    from src.security_lifecycle_web_contract import validate_selection
    from src.ticker_identity_transition import TransitionOptions
    from tests.test_lifecycle_public_sources import Connection, Response
    from tests.test_security_lifecycle_terminal_workflow import setup_workflow
    from tests.test_security_lifecycle_web_finding import NOTICE, finding_payload, public_input

    started = time.monotonic()
    events, sql, phases, polls, heartbeats, decodes = [], [], [], [], [], []
    human_started, second_read_waiting, concurrent_read = Event(), Event(), Event()
    poll_stop = Event()
    run_ids, documents = {}, {}
    report = {"provider_calls": 0, "network_calls": 0, "production_data_access": False,
              "real_controller_heartbeat_and_governed_writer": True, "shared_temporary_profile": True,
              "action": args.action}

    def event(stage, **values):
        item = {"stage": stage, "at_seconds": round(time.monotonic() - started, 3), **values}
        events.append(item)
        print(json.dumps(item), flush=True)

    def denied(*values, **keywords):
        report["network_calls"] += 1
        raise AssertionError("offline_benchmark_attempted_network")

    limit = args.decoded_mib * 1024 * 1024
    first_notice = (NOTICE if args.action == "terminal_delisting" else
        "Issuer Old Inc OLD Class A common stock on NASDAQ changes its ticker from OLD to NEW for the same security effective September 1, 2026.")
    for label, notice in (("first", first_notice), ("second", NOTICE.replace("OLD", "LIVE").replace("Issuer Old Inc", "Issuer Live Inc"))):
        paragraph = ("<p>General layout: " + "\U00020000" * 4000 + "</p>").encode()
        tail = ("<p>" + notice + "</p>" + ("<p>However, the shares remain active OTC.</p>" if label == "second" else "") + "</article>").encode()
        prefix = b"<article><h1>Public notice</h1>"
        count = (limit - len(prefix) - len(tail)) // len(paragraph)
        document = prefix + paragraph * count
        document += b" " * (limit - len(document) - len(tail)) + tail
        assert len(document) == limit
        documents[label] = gzip.compress(document)
        del document, paragraph
    report["document_decoded_bytes"] = limit
    report["document_encoded_bytes"] = {label: len(value) for label, value in documents.items()}
    selected = validate_selection("openai", "api_key", "gpt-5.6-luna", "local:7")
    credential = WebCredential(selected, api_key="synthetic-attended-capacity-only")
    options = pipeline.WebInvestigationOptions(max_sources=4, max_source_requests=8, max_redirects=2,
        max_source_bytes=32 * 1024 * 1024, max_decoded_source_bytes=limit,
        source_timeout_seconds=180, model_timeout_seconds=180, max_search_uses=4,
        output_token_limit=16384, effort="high")
    report["options"] = asdict(options)

    async def model(call, actual, control):
        assert actual is credential
        control.reserve_model_request(call.call_id)
        control.bind_remote_id(call.call_id, "synthetic-" + call.phase)
        label = "second" if "Issuer Live Inc" in call.prompt else "first"
        phases.append({"job": label, "phase": call.phase})
        event("model", job=label, phase=call.phase)
        if call.phase == "search":
            payload = {"sources": [f"https://ir.example.com/{label}/{index}" for index in range(4)], "unresolved_conditions": []}
        elif label == "second":
            payload = finding_payload(source_ticker="LIVE", issuer_name="Issuer Live Inc", contradictions=["Active OTC trading is reported."])
            payload["citations"][0]["quote"] = NOTICE.replace("OLD", "LIVE").replace("Issuer Old Inc", "Issuer Live Inc")
        else:
            payload = finding_payload()
            payload["citations"][0]["quote"] = first_notice
            if args.action == "symbol_continuation":
                payload.update(event_kind="symbol_continuation", successor_ticker="NEW")
                payload["citations"][0]["supports"] = ["security_identity", "same_security_continuation", "effective_date"]
        control.observe_terminal(call.call_id, response_id="synthetic-" + call.phase, status="completed", selection=selected)
        return ModelReply("synthetic-" + call.phase, payload, {"input_tokens": None, "output_tokens": None})

    class FakeConnection(Connection):
        def __init__(self, *values, **keywords):
            super().__init__(Response())

        def request(self, method, path, *, headers):
            label = "second" if "/second/" in path else "first"
            if label == "second" and not concurrent_read.is_set():
                second_read_waiting.set()
                if not concurrent_read.wait(30):
                    raise AssertionError("attended_confirmation_did_not_reach_source_validation")
            body = documents[label]
            self.response = Response(body, headers={"Content-Type": "text/html; charset=utf-8",
                "Content-Encoding": "gzip", "Content-Length": str(len(body))})
            return super().request(method, path, headers=headers)

    connect = sqlite3.connect

    class MeasuredConnection(sqlite3.Connection):
        transaction_at = None

        def execute(self, statement, parameters=()):
            before, error = time.monotonic(), None
            try:
                result = super().execute(statement, parameters)
                if statement == "BEGIN IMMEDIATE":
                    self.transaction_at = time.monotonic()
                return result
            except sqlite3.Error as exc:
                error = str(exc)
                raise
            finally:
                elapsed = time.monotonic() - before
                if elapsed > 0.02 or error:
                    sql.append({"thread": current_thread().name, "operation": " ".join(statement.split())[:100],
                        "at_seconds": round(before - started, 3), "elapsed_seconds": round(elapsed, 3), "error": error})

        def released(self, operation):
            if self.transaction_at is not None:
                sql.append({"thread": current_thread().name, "operation": "write_transaction_" + operation,
                    "at_seconds": round(self.transaction_at - started, 3),
                    "elapsed_seconds": round(time.monotonic() - self.transaction_at, 3), "error": None})
                self.transaction_at = None

        def commit(self):
            result = super().commit()
            self.released("commit")
            return result

        def rollback(self):
            result = super().rollback()
            self.released("rollback")
            return result

        def close(self):
            result = super().close()
            self.released("close")
            return result

    def open_connection(*values, **keywords):
        keywords.setdefault("factory", MeasuredConnection)
        return connect(*values, **keywords)

    decode, heartbeat = LifecycleWebStore._decode_page, LifecycleWebStore.heartbeat

    def measured_decode(row):
        before = time.monotonic()
        if human_started.is_set() and current_thread().name == "attended-confirmation":
            concurrent_read.set()
        try:
            return decode(row)
        finally:
            decodes.append({"thread": current_thread().name, "elapsed_seconds": round(time.monotonic() - before, 3)})

    def measured_heartbeat(store, identity, *, owner):
        before, error = time.monotonic(), None
        try:
            return heartbeat(store, identity, owner=owner)
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            heartbeats.append({"job": next((label for label, run in run_ids.items() if run == identity), "starting"),
                "at_seconds": round(before - started, 3), "elapsed_seconds": round(time.monotonic() - before, 3), "error": error})

    try:
        with tempfile.TemporaryDirectory(prefix="lifecycle-attended-profile-") as temporary, patch.object(
            sqlite3, "connect", open_connection
        ), patch.object(socket, "create_connection", denied), patch.object(socket, "getaddrinfo", denied), patch.object(
            socket.socket, "connect", denied
        ), patch.object(sources, "_PinnedHTTPSConnection", FakeConnection), patch.object(
            sources.PublicSourceReader, "_address", lambda self, host: (2, ("93.184.216.34", 443))
        ), patch.object(pipeline, "call_lifecycle_web_model", model), patch.object(
            LifecycleWebStore, "_decode_page", staticmethod(measured_decode)
        ), patch.object(LifecycleWebStore, "heartbeat", measured_heartbeat):
            c = setup_workflow(Path(temporary), assess=False, event_available=False)
            clock = lambda: datetime.now(timezone.utc).isoformat()
            c["now"][0] = clock()
            for ticker in ("OLD", "LIVE"):
                c["checks"].record(ticker=ticker, at=c["now"][0], evidence=(), diagnostics={}, blockers=("massive_unavailable",))
            with sqlite3.connect(c["profile"]) as conn:
                install_web_journal(conn, at=c["now"][0])
                second_case = SecurityLifecycleInvestigationStore(conn).ensure_case(source="listing_authority", source_ref="listing:LIVE", ticker="LIVE", at=c["now"][0])
            store = LifecycleWebStore(c["profile"])
            controller = LifecycleWebController(store, credential_loader=lambda _: credential)
            request = public_input().model_copy(update={"as_of": c["now"][0][:10], "composite_figi": None})
            first = controller.start(case_id=c["case_id"], observation_sha256=observation_fingerprint(c["checks"].latest()["OLD"]["observation"]),
                request=request, selection=selected, options=options, request_key="attended-first")
            run_ids["first"] = first["run_id"]

            def wait(identity):
                while controller.is_local_running(identity):
                    if time.monotonic() - started > 850:
                        raise TimeoutError("bounded_attended_measurement_timeout")
                    time.sleep(0.1)

            poller = None
            try:
                wait(first["run_id"])
                event("first_completed")
                c["now"][0] = clock()
                transition_options = TransitionOptions(execute_on="2026-09-01")
                packet = prepare(c["service"], first["run_id"], options=transition_options)
                assert packet["ready"], packet["block_reasons"]
                event("packet_prepared")
                second = controller.start(case_id=second_case, observation_sha256=observation_fingerprint(c["checks"].latest()["LIVE"]["observation"]),
                    request=request.model_copy(update={"ticker": "LIVE", "issuer_name": "Issuer Live Inc"}), selection=selected,
                    options=options, request_key="attended-second")
                run_ids["second"] = second["run_id"]
                assert second_read_waiting.wait(15)

                def poll():
                    while not poll_stop.wait(2):
                        before, error, value = time.monotonic(), None, None
                        try:
                            value = controller.read(second["run_id"])
                        except Exception as exc:
                            error = str(exc)
                        polls.append({"elapsed_seconds": round(time.monotonic() - before, 3),
                            "status": None if value is None else value["status"], "error": error})
                        if error or value["status"] not in {"queued", "searching", "reading_sources", "analyzing", "cancelling"}:
                            return

                poller = Thread(target=poll, name="synthetic-progress-poll")
                poller.start()
                before = time.monotonic()
                original_name = current_thread().name
                current_thread().name = "attended-confirmation"
                human_started.set()
                event("human_confirmation_started")
                try:
                    report["receipt"] = confirm(c["service"], first["run_id"], packet_sha256=packet["packet_sha256"],
                        action=args.action, options=transition_options, before_write=lambda: None)
                except Exception as exc:
                    report["confirmation_error"] = str(exc)
                finally:
                    current_thread().name = original_name
                    concurrent_read.set()
                    report["confirmation_elapsed_seconds"] = round(time.monotonic() - before, 3)
                    event("human_confirmation_finished", error=report.get("confirmation_error"))
                wait(second["run_id"])
                poller.join()
                event("second_worker_finished")
                with sqlite3.connect(c["profile"]) as conn:
                    report["statuses"] = [list(row) for row in conn.execute("SELECT status,failure_code FROM lifecycle_web_runs ORDER BY rowid")]
                    report["source_counts"] = [conn.execute("SELECT COUNT(*) FROM lifecycle_web_pages WHERE run_id=?", (identity,)).fetchone()[0] for identity in run_ids.values()]
                    report["acceptances"] = conn.execute("SELECT COUNT(*) FROM lifecycle_web_acceptances").fetchone()[0]
                terminal = controller.read(second["run_id"])
                report["second_receipt"] = {key: terminal[key] for key in ("status", "source_reading", "source_requests")}
                report["active_tickers"] = sorted(c["sources"]())
                report["database_bytes"] = c["profile"].stat().st_size
            finally:
                concurrent_read.set()
                poll_stop.set()
                controller.close()
                if poller is not None:
                    poller.join()
    except Exception as exc:
        report["measurement_error"] = str(exc)
    finally:
        report.update(events=events, sql=sql, model_phases=phases, polls=polls, heartbeats=heartbeats, decodes=decodes,
            peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
            elapsed_seconds=round(time.monotonic() - started, 3))
        report["passed"] = (report.get("receipt", {}).get("status") == "applied"
            and report.get("receipt", {}).get("current_effects_match") is True
            and report.get("statuses") == [["succeeded", None], ["succeeded", None]]
            and report.get("source_counts") == [4, 4]
            and report.get("active_tickers") == (["LIVE"] if args.action == "terminal_delisting" else ["LIVE", "NEW"])
            and report.get("acceptances") == 1 and not report["network_calls"]
            and not any(row["error"] for row in heartbeats + polls + sql)
            and len(phases) == 4 and report.get("second_receipt", {}).get("source_requests") == 4)
        with args.output.open("x") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
    event("measurement_finished", passed=report["passed"])
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

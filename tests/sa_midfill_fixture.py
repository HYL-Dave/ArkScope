"""Private baseline/candidate native stores, also used by installed browser gates."""

from contextlib import AbstractContextManager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import select
import sqlite3
import subprocess
import threading
import time
from uuid import uuid4

from src.sa.company_collector import CompanyCollector
from src.sa.company_store import read_capture, save_capture
from src.sa.article_body_recovery_jobs import BodyRecoveryJobs
from src.sa.article_body_recovery import build_recovery_manifest
from tests.test_sa_company_data import capture
from tests.test_sa_article_body_recovery import article, NARRATIVE

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "b24a2c1d"


def baseline_source(path):
    return subprocess.check_output(["git", "show", f"{BASELINE}:{path}"], cwd=ROOT, text=True)


class UpgradeRig(AbstractContextManager):
    def __init__(self, scope_case, root, monkeypatch, browser="firefox"):
        self.capture, self.profile, self.conn = scope_case
        self.root = root
        monkeypatch.setenv("ARKSCOPE_SA_DB", str(self.capture))
        monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(self.profile))
        self.now = round(time.time(), 3) - 86400
        self.client = {"client_id": ("f" if browser == "firefox" else "c") * 32, "browser": browser}
        self.control_path = self.capture.with_name("sa_company_refresh.db")
        namespace = {"__name__": "tests._sa_midfill_baseline", "__file__": str(ROOT / "src/sa/company_collector.py")}
        exec(compile(baseline_source("src/sa/company_collector.py"), namespace["__file__"], "exec"), namespace)
        self.old_collector = namespace["CompanyCollector"](self.control_path, clock=lambda: self.now)
        self.new_collector = CompanyCollector(self.control_path, clock=lambda: self.now)
        self.collector = self.old_collector
        self.jobs = BodyRecoveryJobs(self.control_path, sa_db=self.capture, profile_db=self.profile, clock=lambda: self.now)
        self.saved, self.navigations, self.messages = [], [], []
        for aid in ("1000", "1001"):
            article(self.conn, aid)
        self.conn.commit()
        self.node = None
        self.server = None

    def __enter__(self):
        rig = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_GET(self):
                self.send_response(200); self.end_headers(); self.wfile.write(b"Offline capture")
            def do_POST(self):
                try:
                    message = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                    response = rig.rpc(message)
                except Exception as exc:
                    response = {"fixture_error": repr(exc)}
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
                self.wfile.write(json.dumps(response).encode())
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        baseline_js = self.root / "baseline-company-refresh.js"
        baseline_js.write_text(baseline_source("extensions/sa_alpha_picks/company_refresh.js"))
        self.node = subprocess.Popen(["node", str(ROOT / "tests/js/run_sa_midfill_worker.mjs"), str(baseline_js),
            str(ROOT / "extensions/sa_alpha_picks/company_refresh.js"), self.url], cwd=ROOT,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return self

    def __exit__(self, *_):
        if self.node:
            self.node.stdin.close()
            try: self.node.wait(timeout=5)
            except subprocess.TimeoutExpired: self.node.terminate(); self.node.wait(timeout=5)
        if self.server:
            self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=3)

    def control(self, operation, **extra):
        return self.collector.handle({"operation": operation, "client": self.client, **extra})

    def rpc(self, message):
        self.messages.append(message)
        operation = message.get("operation")
        if operation == "fixture_save":
            scope = message["scope"]
            payload = capture(scope["statement"].replace("_", "-"), ticker=scope["ticker"])
            payload["captured_at"] = datetime.fromtimestamp(self.now, timezone.utc).isoformat()
            return save_capture(payload, db_path=self.capture)
        if operation == "fixture_receipt":
            scope = message["scope"]
            self.saved.append({"scope_id": "/".join(scope[k] for k in ("ticker", "statement", "view")),
                               "scope": scope, "receipt": message["receipt"]})
            return {"status": "ok"}
        if operation == "fixture_clock":
            return {"now": self.now * 1000}
        if message.get("action") == "preview_article_body_recovery":
            return {**build_recovery_manifest(self.capture), "protocol_version": 2}
        if message.get("action") == "article_body_recovery_control":
            return self.jobs.handle(message, client=message["client"])
        if operation == "fixture_body_save":
            with sqlite3.connect(self.capture) as conn:
                conn.execute("UPDATE sa_articles SET body_markdown=? WHERE article_id=?", (NARRATIVE, message["article_id"]))
            return {"status": "ok", "body_saved": True}
        reply = self.collector.handle(message)
        if operation == "admit_navigation" and reply.get("allowed"):
            self.navigations.append(message)
        return reply

    def worker(self, operation, **extra):
        self.node.stdin.write(json.dumps({"operation": operation, **extra}) + "\n"); self.node.stdin.flush()
        assert select.select([self.node.stdout], [], [], 15)[0], "financial worker timed out"
        reply = json.loads(self.node.stdout.readline())
        assert "fixture_error" not in reply, reply
        return reply

    def initialize(self, scheduled=False):
        reply = self.control("configure", expected_generation=0, confirm_activation=True, financial_gap_seconds=60,
            policy={"hour_limit": None, "day_limit": None, "hour_reserve": 0, "day_reserve": 0})
        assert reply["status"] == "ok", reply
        reply = self.control("select", expected_generation=reply["generation"], confirm_schedules=True)
        assert reply["status"] == "ok", reply
        return self.worker("initialize", now=self.now * 1000, client=self.client, scheduled=scheduled)

    def native_checkpoint(self):
        with sqlite3.connect(self.control_path) as conn:
            return json.loads(conn.execute("SELECT payload FROM company_collector WHERE id=1").fetchone()[0])

    def checkpoint(self):
        return {"browser": self.worker("snapshot")["browser"], "native": self.native_checkpoint()}

    def reload(self, version):
        self.collector = self.new_collector if version == "candidate" else self.old_collector
        return self.worker("reload", version=version)

    def advance(self, seconds):
        self.now += seconds
        self.worker("clock", now=self.now * 1000)

    def run_financial(self): return self.worker("run")
    def seed_retry_on_last_pending(self): return self.worker("retry")

    def verify_captures(self):
        for row in self.saved:
            scope = row["scope"]
            receipt = row["receipt"]
            assert receipt["active"] is None
            with sqlite3.connect(self.control_path) as conn:
                task = conn.execute("SELECT payload, finished_at, receipt FROM acquisition_tasks WHERE task_id=?",
                                    (receipt["acquisition"]["task_id"],)).fetchone()
            assert task[1] is not None
            assert json.loads(task[2]) == receipt["acquisition"]
            stored = read_capture(scope["ticker"], scope["statement"], scope["view"], "USD", db_path=self.capture)
            assert stored["observation_id"] == json.loads(task[0])["result"]["observation_id"]

    def body_call(self, operation, **extra):
        return self.jobs.handle({"protocol_version": 2, "operation": operation, "expected_generation": 1, **extra}, client=self.client)

    def start_body(self):
        manifest = build_recovery_manifest(self.capture)
        result = self.body_call("start", trigger="manual", request_id=uuid4().hex, manifest_id=manifest["manifest_id"])
        assert result["status"] == "ok", result
        return result

    def run_body(self, job):
        task = self.control("begin_task", generation=1, request_id=uuid4().hex, task_operation="alpha_picks_body_repair",
            mode="manual", trigger="continuation", intent_revision=job["revision"], build="midfill-test", protocol_version=2,
            body_job_id=job["job_id"], body_job_revision=job["revision"], article_id="1000")
        assert task["status"] == "ok", task
        navigation = self.control("admit_navigation", token=task["token"], generation=1,
            navigation_id=uuid4().hex, kind="create", destination_class="article")
        assert navigation.get("allowed"), navigation
        self.rpc({"operation": "fixture_body_save", "article_id": "1000"})
        reply = self.control("finish_task", token=task["token"], generation=1, cleanup_confirmed=True, result={"status": "ok"})
        assert reply["status"] == "ok", reply
        return reply

    def cancel_body(self, job):
        result = self.body_call("cancel", job_id=job["job_id"], revision=job["revision"])
        assert result["state"] == "cancelled", result

    def body_status(self): return self.jobs.public_status()
    def body_is_saved(self):
        return self.conn.execute("SELECT body_markdown FROM sa_articles WHERE article_id='1000'").fetchone()[0] == NARRATIVE

    def run_news(self):
        task = self.control("begin_task", generation=1, request_id=uuid4().hex, task_operation="market_news_sync",
            mode="quick", trigger="manual", intent_revision=1, build="midfill-test", protocol_version=2)
        assert task["status"] == "ok", task
        done = self.control("finish_task", token=task["token"], generation=1, cleanup_confirmed=True, result={"status": "ok"})
        assert done["acquisition"]["priority"] == "routine"
        assert done["active"] is None

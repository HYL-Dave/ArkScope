"""Standalone SQLite probes. No application imports, providers, or real stores."""

import argparse
from contextlib import closing, contextmanager
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import sqlite3
import _sqlite3
import subprocess
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parent
SOURCE_ID = "2026-07-24 19:02:57 bf7c7f30031888f4e796e429ab3978879485813aaca6f641c7b33e4e09459bcc"
DECIMAL_TEXT = "12345678901234567890.12345678901234567890"


def contained(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("refusing path outside authorized scratch")
    return path


def audit(event, args):
    if event == "sqlite3.connect":
        path = os.fsdecode(args[0])
        if path != ":memory:":
            contained(path)


sys.addaudithook(audit)


@contextmanager
def connect(path=":memory:", *, isolation_level=None, timeout=5):
    with closing(sqlite3.connect(path, isolation_level=isolation_level, timeout=timeout)) as conn:
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA foreign_keys=ON")
        yield conn


def sql_identity():
    with connect() as conn:
        return conn.execute("SELECT sqlite_version(), sqlite_source_id()").fetchone()


def identity(expected):
    version, source = sql_identity()
    with connect() as conn:
        options = sorted(row[0] for row in conn.execute("PRAGMA compile_options"))
    mapped = sorted({line.split()[-1] for line in Path("/proc/self/maps").read_text().splitlines()
                     if "/libsqlite3.so" in line})
    report = {
        "python_executable": sys.executable,
        "python_version": sys.version,
        "python_flags": {"isolated": sys.flags.isolated, "no_site": sys.flags.no_site,
                         "dont_write_bytecode": sys.flags.dont_write_bytecode},
        "platform": list(os.uname()),
        "sqlite_extension": _sqlite3.__file__,
        "sqlite_extension_sha256": hashlib.sha256(Path(_sqlite3.__file__).read_bytes()).hexdigest(),
        "sqlite_version": version,
        "sqlite_source_id": source,
        "mapped_sqlite_libraries": mapped,
        "mapped_library_sha256": {path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
                                  for path in mapped},
        "compile_options": options,
        "probe_ld_library_path": os.environ.get("LD_LIBRARY_PATH"),
    }
    print(json.dumps({"identity": report}), flush=True)
    assert not sys.flags.optimize
    assert all(report["python_flags"].values())
    assert version == expected, "wrong runtime; stop before synthetic database writes"
    assert "ENABLE_FTS5" in options and "THREADSAFE=1" in options
    if expected == "3.53.4":
        assert source == SOURCE_ID, "candidate source ID mismatch; stop"
        assert mapped == [str(ROOT / "package/lib/libsqlite3.so.3.53.4")], "wrong mapped library"
    else:
        assert not os.environ.get("LD_LIBRARY_PATH")
        assert mapped and all(not Path(path).is_relative_to(ROOT) for path in mapped)
    return report


def check_integrity(conn):
    assert conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def json_decimal_text(root):
    with connect(root / "decimal.db") as conn:
        conn.execute("CREATE TABLE facts(value TEXT NOT NULL, details TEXT NOT NULL CHECK(json_valid(details)))")
        payload = json.dumps({"amount": DECIMAL_TEXT, "items": [1, "x"], "null": None})
        conn.execute("INSERT INTO facts VALUES(?,?)", (DECIMAL_TEXT, payload))
        row = conn.execute("SELECT value,typeof(value),json_extract(details,'$.amount'),"
                           "typeof(json_extract(details,'$.amount')),json_type(details,'$.amount') FROM facts").fetchone()
        assert row == (DECIMAL_TEXT, "text", DECIMAL_TEXT, "text", "text")
        assert Decimal(row[0]) == Decimal("12345678901234567890.12345678901234567890")
        assert conn.execute("SELECT value,type FROM json_each(?, '$.items') ORDER BY key", (payload,)).fetchall() == [(1, "integer"), ("x", "text")]
        assert conn.execute("SELECT json_extract(?, '$.null'),json_type(?, '$.null')", (payload, payload)).fetchone() == (None, "null")
        conn.execute("UPDATE facts SET value=?, details=json_set(details,'$.amount',?)",
                     ("1.230000000000000000", "1.230000000000000000"))
        assert conn.execute("SELECT value,json_extract(details,'$.amount') FROM facts").fetchone() == ("1.230000000000000000", "1.230000000000000000")
        try:
            conn.execute("INSERT INTO facts VALUES('invalid','{bad')")
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("JSON CHECK did not reject invalid JSON")
        check_integrity(conn)
    return {"exact_decimal_text": DECIMAL_TEXT, "trailing_zeros_preserved": True, "invalid_json_rejected": True}


def fts_external_content(root):
    with connect(root / "fts.db") as conn:
        conn.executescript("""
            CREATE TABLE documents(id INTEGER PRIMARY KEY, title TEXT, body TEXT);
            CREATE VIRTUAL TABLE documents_fts USING fts5(title, body,
                content='documents', content_rowid='id', tokenize='porter unicode61');
            CREATE TRIGGER documents_ai AFTER INSERT ON documents BEGIN
                INSERT INTO documents_fts(rowid,title,body) VALUES(new.id,new.title,new.body);
            END;
            CREATE TRIGGER documents_ad AFTER DELETE ON documents BEGIN
                INSERT INTO documents_fts(documents_fts,rowid,title,body)
                    VALUES('delete',old.id,old.title,old.body);
            END;
            CREATE TRIGGER documents_au AFTER UPDATE ON documents BEGIN
                INSERT INTO documents_fts(documents_fts,rowid,title,body)
                    VALUES('delete',old.id,old.title,old.body);
                INSERT INTO documents_fts(rowid,title,body) VALUES(new.id,new.title,new.body);
            END;
        """)
        conn.executemany("INSERT INTO documents VALUES(?,?,?)",
                         [(1, "Running markets", "caf\u00e9 na\u00efve"), (2, "Filing", "quarter")])
        def hits(term):
            return conn.execute("SELECT rowid FROM documents_fts WHERE documents_fts MATCH ? ORDER BY rowid", (term,)).fetchall()
        assert hits("run") == [(1,)]
        assert hits("cafe") == [(1,)] and hits("naive") == [(1,)]
        conn.execute("UPDATE documents SET title='Walking',body='updated' WHERE id=1")
        assert hits("run") == [] and hits("cafe") == [] and hits("walk") == [(1,)]
        conn.execute("DELETE FROM documents WHERE id=2")
        assert hits("filing") == [] and hits("quarter") == []
        conn.execute("INSERT INTO documents_fts(documents_fts,rank) VALUES('integrity-check',1)")
        check_integrity(conn)
    return {"porter_stemming": True, "unicode61_diacritics": True,
            "insert_update_delete_triggers": True, "fts_external_content_integrity": "ok"}


def foreign_keys(root):
    with connect(root / "foreign_keys.db") as conn:
        conn.executescript("CREATE TABLE parent(id INTEGER PRIMARY KEY);"
                           "CREATE TABLE child(id INTEGER PRIMARY KEY,pid INTEGER REFERENCES parent(id) ON DELETE CASCADE);")
        assert conn.execute("PRAGMA foreign_keys").fetchone() == (1,)
        try:
            conn.execute("INSERT INTO child VALUES(1,99)")
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("orphan insert was accepted")
        conn.execute("INSERT INTO parent VALUES(1)")
        conn.execute("INSERT INTO child VALUES(1,1)")
        conn.execute("DELETE FROM parent WHERE id=1")
        assert conn.execute("SELECT count(*) FROM child").fetchone() == (0,)
        check_integrity(conn)
    return {"orphan_rejected": True, "delete_cascade": True, "foreign_key_check": []}


def transactions(root):
    with connect(root / "transactions.db", isolation_level="DEFERRED") as conn:
        conn.execute("CREATE TABLE events(id INTEGER PRIMARY KEY,value TEXT)")
        with conn:
            conn.execute("INSERT INTO events VALUES(1,'original')")
            conn.execute("SAVEPOINT nested")
            conn.execute("UPDATE events SET value='discarded' WHERE id=1")
            conn.execute("ROLLBACK TO nested")
            conn.execute("RELEASE nested")
        try:
            with conn:
                conn.execute("INSERT INTO events VALUES(2,'rolled back')")
                conn.execute("INSERT INTO events VALUES(1,'duplicate')")
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("duplicate primary key accepted")
        assert conn.execute("SELECT * FROM events ORDER BY id").fetchall() == [(1, "original")]
        assert not conn.in_transaction
        check_integrity(conn)
    return {"commit": True, "savepoint_rollback": True, "exception_context_rollback": True}


def send(proc, message):
    proc.stdin.write(message + "\n")
    proc.stdin.flush()


def receive(proc):
    with selectors.DefaultSelector() as selector:
        selector.register(proc.stdout, selectors.EVENT_READ)
        assert selector.select(timeout=10), "worker readiness timeout"
        line = proc.stdout.readline()
    assert line, "worker exited before readiness"
    return json.loads(line)


@contextmanager
def worker(kind, database, worker_id=0):
    env = {key: os.environ[key] for key in (
        "PATH", "HOME", "TMPDIR", "LC_ALL", "PYTHONDONTWRITEBYTECODE", "LD_LIBRARY_PATH") if key in os.environ}
    proc = subprocess.Popen([sys.executable, "-I", "-S", "-B", str(Path(__file__).resolve()),
                             "worker", "--worker-kind", kind, "--database", str(contained(database)),
                             "--worker-id", str(worker_id)], cwd=ROOT, env=env,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True)
    try:
        ready = receive(proc)
        assert ready["ready"] is True and (ready["version"], ready["source_id"]) == sql_identity()
        yield proc
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            if stream:
                stream.close()


def finish(proc):
    if proc.stdin:
        proc.stdin.close()
        proc.stdin = None
    stdout, stderr = proc.communicate(timeout=45)
    assert proc.returncode == 0, f"worker exit {proc.returncode}: {stderr}"
    assert not stderr, stderr
    return json.loads(stdout)


def wal_locking(root):
    path = root / "locking.db"
    with connect(path) as keeper, connect(path) as reader, connect(path, timeout=0.15) as contender:
        assert keeper.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        keeper.execute("PRAGMA wal_autocheckpoint=0")
        keeper.execute("CREATE TABLE held(id INTEGER PRIMARY KEY,value TEXT)")
        keeper.execute("INSERT INTO held VALUES(1,'original')")
        reader.execute("BEGIN")
        assert reader.execute("SELECT count(*) FROM held").fetchone() == (1,)
        with worker("hold", path, 2) as child:
            started = time.monotonic()
            try:
                contender.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError as exc:
                elapsed = time.monotonic() - started
                assert "locked" in str(exc).lower()
                assert 0.10 <= elapsed < 5
            else:
                raise AssertionError("concurrent writer acquired an exclusive write transaction")
            assert keeper.execute("SELECT count(*) FROM held").fetchone() == (1,)
            send(child, "commit")
            assert finish(child)["committed"] is True
        assert reader.execute("SELECT count(*) FROM held").fetchone() == (1,)
        assert keeper.execute("SELECT count(*) FROM held").fetchone() == (2,)
        reader.execute("COMMIT")
        assert reader.execute("SELECT count(*) FROM held").fetchone() == (2,)
        with worker("hold", path, 3) as child:
            child.kill()
            crash_exit = child.wait(timeout=10)
            assert crash_exit == -9
        contender.execute("BEGIN IMMEDIATE")
        contender.execute("ROLLBACK")
        assert keeper.execute("SELECT id FROM held ORDER BY id").fetchall() == [(1,), (2,)]
        check_integrity(keeper)
    return {"busy_wait_seconds": round(elapsed, 6), "reader_snapshot_preserved": True,
            "uncommitted_crash_exit": crash_exit, "post_crash_lock_reacquired": True, "rows": 2}


def wal_concurrency(root):
    from contextlib import ExitStack
    path = root / "concurrency.db"
    with connect(path) as keeper, ExitStack() as stack:
        assert keeper.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        keeper.execute("PRAGMA wal_autocheckpoint=0")
        keeper.execute("CREATE TABLE ledger(worker INTEGER,n INTEGER,value TEXT,PRIMARY KEY(worker,n))")
        writers = [stack.enter_context(worker("write", path, number)) for number in range(3)]
        checkpoint = stack.enter_context(worker("checkpoint", path))
        for proc in writers + [checkpoint]:
            send(proc, "start")
        results = [finish(proc) for proc in writers]
        checkpoints = finish(checkpoint)
        assert [row["commits"] for row in results] == [100, 100, 100]
        assert checkpoints["attempts"] == 150 and checkpoints["partial_observations"] > 0
        expected = [(0, 100, 4950), (1, 100, 4950), (2, 100, 4950)]
        assert keeper.execute("SELECT worker,count(*),sum(n) FROM ledger GROUP BY worker ORDER BY worker").fetchall() == expected
        assert keeper.execute("SELECT count(*) FROM ledger WHERE value='0.10000000000000000001' AND typeof(value)='text'").fetchone() == (300,)
        final_checkpoint = keeper.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        assert final_checkpoint == (0, 0, 0)
        check_integrity(keeper)
    return {"writers": results, "checkpoints": checkpoints, "group_counts_sums": expected,
            "final_checkpoint": final_checkpoint, "integrity_check": "ok",
            "limitation": "bounded stress, not a deterministic upstream WAL-reset reproducer"}


def backup_uncheckpointed_wal(root):
    source = root / "backup_source.db"
    destination = root / "backup_destination.db"
    main_only = root / "main_file_negative_control.db"
    with connect(source) as conn:
        assert conn.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        conn.execute("PRAGMA wal_autocheckpoint=0")
        conn.execute("CREATE TABLE records(id INTEGER PRIMARY KEY,value TEXT)")
        conn.execute("INSERT INTO records VALUES(1,'checkpointed')")
        assert conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone() == (0, 0, 0)
        conn.executemany("INSERT INTO records VALUES(?,?)", [(2, DECIMAL_TEXT), (3, "uncheckpointed")])
        wal_bytes = Path(str(source) + "-wal").stat().st_size
        assert wal_bytes > 32
        # This deliberately incomplete copy is a negative control, not a backup method.
        shutil.copyfile(source, main_only)
        with connect(main_only) as incomplete:
            assert incomplete.execute("SELECT * FROM records").fetchall() == [(1, "checkpointed")]
        os.close(os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
        progress = []
        with connect(destination) as copied:
            conn.backup(copied, pages=1, progress=lambda *args: progress.append(args))
            assert copied.execute("SELECT * FROM records ORDER BY id").fetchall() == [(1, "checkpointed"), (2, DECIMAL_TEXT), (3, "uncheckpointed")]
            assert progress[-1][0] == 101 and progress[-1][1] == 0
            check_integrity(copied)
        check_integrity(conn)
    return {"uncheckpointed_wal_bytes": wal_bytes, "main_only_rows": 1, "backup_rows": 3,
            "progress": progress, "integrity_check": "ok"}


def posix_process_lock(root):
    import fcntl
    path = root / "process.lock"
    with path.open("a+") as handle:
        with worker("flock", path) as child:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                raise AssertionError("flock failed to exclude another process")
            child.kill()
            assert child.wait(timeout=10) == -9
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(handle, fcntl.LOCK_UN)
    return {"cross_process_exclusion": True, "released_after_sigkill": True, "platform": "Linux only"}


def worker_main(args):
    path = contained(args.database)
    version, source = sql_identity()
    def ready():
        print(json.dumps({"ready": True, "version": version, "source_id": source}), flush=True)
    if args.worker_kind == "flock":
        import fcntl
        with path.open("a+") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            ready()
            sys.stdin.readline()
        return
    with connect(path, timeout=5) as conn:
        conn.execute("PRAGMA wal_autocheckpoint=0")
        if args.worker_kind == "hold":
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT INTO held VALUES(?,'worker')", (args.worker_id,))
            ready()
            assert sys.stdin.readline().strip() == "commit"
            conn.execute("COMMIT")
            print(json.dumps({"committed": True}), flush=True)
        else:
            ready()
            assert sys.stdin.readline().strip() == "start"
            if args.worker_kind == "write":
                for number in range(100):
                    conn.execute("BEGIN IMMEDIATE")
                    conn.execute("INSERT INTO ledger VALUES(?,?,'0.10000000000000000001')", (args.worker_id, number))
                    conn.execute("COMMIT")
                    time.sleep(0.005)
                print(json.dumps({"worker": args.worker_id, "commits": 100}), flush=True)
            else:
                conn.execute("PRAGMA busy_timeout=50")
                observations = []
                outcomes = []
                for number in range(150):
                    mode = ("PASSIVE", "RESTART", "TRUNCATE")[number % 3]
                    outcomes.append((mode, *conn.execute(f"PRAGMA wal_checkpoint({mode})").fetchone()))
                    observations.append(conn.execute("SELECT count(*) FROM ledger").fetchone()[0])
                    time.sleep(0.005)
                print(json.dumps({"attempts": 150, "mode_attempts": {mode: 50 for mode in ("PASSIVE", "RESTART", "TRUNCATE")},
                                  "busy_results": sum(row[1] != 0 for row in outcomes),
                                  "complete_checkpoints": sum(row[1] == 0 and row[2] == row[3] for row in outcomes),
                                  "partial_observations": sum(0 < value < 300 for value in observations),
                                  "observed_rows_min": min(observations), "observed_rows_max": max(observations)}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("identity", "suite", "worker"))
    parser.add_argument("--expected-version", choices=("3.37.2", "3.53.4"))
    parser.add_argument("--run-name")
    parser.add_argument("--worker-kind", choices=("hold", "write", "checkpoint", "flock"))
    parser.add_argument("--database")
    parser.add_argument("--worker-id", type=int, default=0)
    args = parser.parse_args()
    if args.mode == "worker":
        worker_main(args)
        return 0
    identity(args.expected_version)
    if args.mode == "identity":
        return 0
    assert args.run_name and re.fullmatch(r"[a-zA-Z0-9_-]+", args.run_name)
    root = contained(ROOT / "tmp" / args.run_name)
    root.mkdir(mode=0o700, exist_ok=False)
    cases = (json_decimal_text, fts_external_content, foreign_keys, transactions,
             wal_locking, wal_concurrency, backup_uncheckpointed_wal, posix_process_lock)
    results = []
    for test in cases:
        started = time.monotonic()
        try:
            result = {"test": test.__name__, "result": "pass", "details": test(root)}
        except Exception as exc:
            result = {"test": test.__name__, "result": "fail", "error": str(exc),
                      "traceback": traceback.format_exc()}
        result["elapsed_seconds"] = round(time.monotonic() - started, 6)
        results.append(result)
        print(json.dumps(result), flush=True)
    passed = sum(result["result"] == "pass" for result in results)
    print(json.dumps({"summary": {"passed": passed, "failed": len(results) - passed,
                                  "scratch_databases": str(root), "application_admitted": False}}), flush=True)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())

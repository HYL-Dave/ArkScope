"""Observe Research commit gaps offline; not a passing-fix acceptance test."""

from __future__ import annotations

import asyncio
from contextlib import nullcontext
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from unittest.mock import patch
from urllib.parse import unquote


REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))


class SimulatedCommitInterruption(RuntimeError):
    pass


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="arkscope-continuity-audit-") as raw:
        root = Path(raw).resolve()

        def guard(event, args):
            if event in {"socket.connect", "subprocess.Popen"}:
                raise AssertionError("This observation must remain offline")
            if event != "sqlite3.connect":
                return
            value = os.fsdecode(os.fspath(args[0]))
            if value == ":memory:":
                return
            if value.startswith("file:"):
                value = unquote(value.removeprefix("file:").split("?", 1)[0])
            if not Path(value).resolve().is_relative_to(root):
                raise AssertionError("SQLite access outside the private fixture")

        sys.addaudithook(guard)
        env = {
            "ARKSCOPE_PROFILE_DB": str(root / "profile_state.db"),
            "ARKSCOPE_MARKET_DB": str(root / "market_data.db"),
            "ARKSCOPE_SA_DB": str(root / "sa_capture.db"),
            "ARKSCOPE_MACRO_CALENDAR_DB": str(root / "macro_calendar.db"),
            "ARKSCOPE_CONSENSUS_DB": str(root / "consensus.db"),
            "ARKSCOPE_LOCK_DIR": str(root / "locks"),
            "ARKSCOPE_DISABLE_SCHEDULER": "1",
        }
        with patch.dict(os.environ, env):
            from src.agents.shared.events import AgentEvent, EventType
            from src.auth_drivers.runtime_binding import RuntimeAuthBinding
            from src.research_run_manager import execute_research_run
            from src.research_runs import ResearchRunStore
            from src.research_threads import ResearchThreadStore, build_thread_history

            observations = []
            for mode in ("control", "assistant_write_failure", "interrupted_before_terminal"):
                db = root / f"{mode}.db"
                runs, threads = ResearchRunStore(db), ResearchThreadStore(db)
                threads.ensure_thread(id="thread", title="Synthetic continuity audit")
                runs.create_run(
                    id="run", thread_id="thread", question="Synthetic question",
                    ticker=None, provider="openai", model="synthetic-model", effort="low",
                    auth_mode="api_key", credential_id="local:synthetic",
                )
                threads.append_message(
                    thread_id="thread", run_id="run", role="user", content="Synthetic question",
                )
                dispatches = 0

                async def stream_factory(**kwargs):
                    nonlocal dispatches
                    dispatches += 1
                    yield AgentEvent(EventType.done, {
                        "answer": "Synthetic answer", "provider": "openai",
                        "model": "synthetic-model", "tools_used": [],
                    })

                fault = nullcontext()
                if mode == "assistant_write_failure":
                    fault = patch.object(
                        threads, "append_message",
                        side_effect=sqlite3.OperationalError("injected assistant-write failure"),
                    )
                elif mode == "interrupted_before_terminal":
                    fault = patch.object(
                        runs, "mark_terminal", side_effect=SimulatedCommitInterruption,
                    )
                interrupted = False
                with fault:
                    try:
                        asyncio.run(execute_research_run(
                            run_id="run", run_store=runs, thread_store=threads,
                            dal=object(), history=[], stream_factory=stream_factory,
                            auth_binding=RuntimeAuthBinding(
                                "openai", "db_api_key", "api_key", "local:synthetic",
                                _api_key="synthetic-offline-key",
                            ),
                        ))
                    except SimulatedCommitInterruption:
                        interrupted = True
                messages = threads.list_messages("thread")
                before = {
                    "status": runs.get_run("run").status,
                    "assistant_messages": sum(message.role == "assistant" for message in messages),
                    "events": [event.type for event in runs.list_events("run")],
                }
                runs, threads = ResearchRunStore(db), ResearchThreadStore(db)
                runs.reconcile_interrupted(thread_store=threads)
                after_messages = threads.list_messages("thread")
                after = {
                    "status": runs.get_run("run").status,
                    "assistant_messages": sum(message.role == "assistant" for message in after_messages),
                    "error_messages": sum(message.is_error for message in after_messages),
                    "events": [event.type for event in runs.list_events("run")],
                    "history_roles": [message["role"] for message in build_thread_history(threads, "thread")],
                }
                assert dispatches == 1
                if mode == "control":
                    assert before == {"status": "succeeded", "assistant_messages": 1, "events": ["done"]}
                    assert after["error_messages"] == 0
                observations.append({
                    "case": mode, "provider_dispatches": dispatches,
                    "interruption_injected": interrupted,
                    "before_restart": before, "after_restart": after,
                })
            print(json.dumps({
                "scope": "synthetic-only; SQLite paths and network guarded",
                "meaning": "observations, not acceptance that the defects are fixed",
                "observations": observations,
            }, indent=2))


if __name__ == "__main__":
    main()

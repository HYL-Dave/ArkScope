"""Network-free app-server protocol peer for process-boundary tests only."""

import json
import os
from pathlib import Path
import sys


if sys.argv[1:] == ["--version"]:
    print("codex-cli 0.147.0", flush=True)
    raise SystemExit(0)

root = Path(sys.argv[0]).parent
(root / "web-peer.pid").write_text(str(os.getpid()))
config = {}
args = iter(sys.argv[1:-3])
for arg in args:
    assert arg == "-c"
    key, raw = next(args).split("=", 1)
    target = config
    parts = key.split(".")
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = json.loads(raw)


def emit(value):
    print(json.dumps(value), flush=True)


for line in sys.stdin:
    request = json.loads(line)
    method, params = request["method"], request.get("params", {})
    with (root / "web-peer.jsonl").open("a") as handle:
        handle.write(json.dumps({"method": method, "environment_keys": sorted(os.environ),
                                 "config": config, "home": os.environ["CODEX_HOME"]}) + "\n")
    if method == "initialized":
        continue
    identity = request["id"]
    if method == "initialize":
        result = {"codexHome": os.environ["CODEX_HOME"]}
    elif method == "account/login/start":
        assert params["type"] == "chatgptAuthTokens"
        result = {"type": "chatgptAuthTokens"}
    elif method == "account/read":
        result = {"account": {"type": "chatgpt", "planType": "prolite"}, "requiresOpenaiAuth": True}
    elif method == "config/read":
        result = {"config": config, "layers": None, "origins": {}}
    elif method == "model/list":
        result = {"data": [{"id": "fixture", "model": "gpt-5.6-luna"}], "nextCursor": None}
    elif method == "thread/start":
        assert params["dynamicTools"] == [] and params["environments"] == []
        assert params["allowProviderModelFallback"] is False
        thread = {"id": "thread-1", "cwd": params["cwd"], "ephemeral": True,
                  "modelProvider": "openai", "parentThreadId": None}
        result = {"thread": thread, "cwd": params["cwd"], "model": params["model"],
                  "modelProvider": "openai", "approvalPolicy": "never", "approvalsReviewer": "user",
                  "sandbox": {"type": "readOnly", "networkAccess": False}, "reasoningEffort": "high",
                  "instructionSources": [], "runtimeWorkspaceRoots": []}
        emit({"id": identity, "result": result})
        emit({"method": "thread/started", "params": {"thread": thread}})
        continue
    elif method == "turn/start":
        result = {"turn": {"id": "turn-1", "status": "inProgress", "items": []}}
        emit({"id": identity, "result": result})
        common = {"threadId": "thread-1", "turnId": "turn-1"}
        emit({"method": "turn/started", "params": {**common, **result}})
        if config["web_search"] == "live":
            emit({"method": "item/completed", "params": {**common, "item": {
                "type": "webSearch", "id": "web-1", "action": {"type": "search"}, "query": "Issuer Old Inc"}}})
        emit({"method": "item/completed", "params": {**common, "item": {
            "type": "agentMessage", "id": "final-1", "phase": "final_answer",
            "text": '{"sources":["https://ir.example.com/notice"]}'}}})
        emit({"method": "turn/completed", "params": {**common, "turn": {
            "id": "turn-1", "status": "completed", "items": []}}})
        continue
    else:
        raise AssertionError(method)
    emit({"id": identity, "result": result})

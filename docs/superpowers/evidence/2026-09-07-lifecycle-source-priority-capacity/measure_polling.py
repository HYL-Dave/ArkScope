"""Exercise real progress reads during the two-job synthetic capacity workload."""

import argparse
import importlib.util
import json
from pathlib import Path
import sys
from threading import Event, Thread
import time
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args, _ = parser.parse_known_args()
    sys.path.insert(0, str(args.repo.resolve()))
    from src import lifecycle_web_controller as controller_module

    spec = importlib.util.spec_from_file_location("capacity_runtime", Path(__file__).with_name("measure_runtime.py"))
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    observations = []

    class ObservedController(controller_module.LifecycleWebController):
        def __init__(self, *values, **keywords):
            super().__init__(*values, **keywords)
            self.polling_stop = Event()
            self.pollers = []

        def start(self, **request):
            receipt = super().start(**request)

            def poll():
                while not self.polling_stop.wait(2):
                    started = time.monotonic()
                    try:
                        value = self.read(receipt["run_id"])
                        result = {"status": value["status"], "error": None}
                    except Exception as exc:
                        result = {"status": None, "error": str(exc)}
                    observations.append({**result, "case_id": request["case_id"],
                                         "elapsed_seconds": round(time.monotonic() - started, 3)})
                    if result["error"] is not None or result["status"] not in {
                        "queued", "searching", "reading_sources", "analyzing", "cancelling",
                    }:
                        return

            thread = Thread(target=poll, name="synthetic-ui-progress")
            self.pollers.append(thread)
            thread.start()
            return receipt

        def close(self):
            try:
                super().close()
                for thread in self.pollers:
                    thread.join()
            finally:
                self.polling_stop.set()

    try:
        with patch.object(controller_module, "LifecycleWebController", ObservedController):
            runtime.main()
    finally:
        with args.output.with_name("polling.json").open("x") as stream:
            json.dump({"provider_calls": 0, "production_data_access": False, "observations": observations},
                      stream, indent=2, sort_keys=True)
            stream.write("\n")


if __name__ == "__main__":
    main()

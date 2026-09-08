"""Reuse the sealed source-only campaign runner with this operation's owners."""

import importlib.util
from pathlib import Path

here = Path(__file__).resolve()
runner = here.parents[2] / "2026-09-06-recent-price-repair/scripts/run_mutations.py"
spec = importlib.util.spec_from_file_location("recent_price_campaign", runner)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.PACKET = here.parents[1]

if __name__ == "__main__":
    module.main()

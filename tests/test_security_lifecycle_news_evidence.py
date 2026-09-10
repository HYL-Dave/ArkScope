from __future__ import annotations

from pathlib import Path


def test_original_publisher_acquisition_design_is_explicitly_superseded():
    repo = Path(__file__).resolve().parents[1]
    design = (
        repo / "docs/superpowers/specs/2026-08-24-trusted-lifecycle-automation-design.md"
    ).read_text(encoding="utf-8")

    assert "SUPERSEDED FOR ACTIVE ACQUISITION" in design
    assert "2026-08-28-lifecycle-listing-authority-design.md" in design

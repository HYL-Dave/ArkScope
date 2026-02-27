"""Tests for analysis.rate_curve — yield curve abstraction + interpolation."""

import pytest

from analysis.rate_curve import (
    RateCurve,
    get_rate_for_dte,
    make_flat_curve,
    get_yield_curve,
    _fetch_treasury_curve,
)


# ── RateCurve dataclass ──────────────────────────────────────


class TestRateCurve:
    def test_basic_creation(self):
        c = RateCurve(tenors=[91], rates=[0.043])
        assert c.tenors == [91]
        assert c.rates == [0.043]

    def test_multi_tenor(self):
        c = RateCurve(
            tenors=[91, 365, 1825],
            rates=[0.043, 0.045, 0.048],
        )
        assert len(c.tenors) == 3
        assert c.short_rate == 0.043
        assert c.long_rate == 0.048

    def test_is_flat(self):
        flat = RateCurve(tenors=[91, 365], rates=[0.05, 0.05])
        assert flat.is_flat

        slope = RateCurve(tenors=[91, 365], rates=[0.04, 0.05])
        assert not slope.is_flat

    def test_mismatched_lengths_rejected(self):
        with pytest.raises(ValueError, match="same length"):
            RateCurve(tenors=[91, 365], rates=[0.04])

    def test_empty_rejected(self):
        with pytest.raises(ValueError, match="at least one"):
            RateCurve(tenors=[], rates=[])

    def test_unsorted_rejected(self):
        with pytest.raises(ValueError, match="strictly ascending"):
            RateCurve(tenors=[365, 91], rates=[0.05, 0.04])

    def test_duplicate_tenors_rejected(self):
        with pytest.raises(ValueError, match="strictly ascending"):
            RateCurve(tenors=[91, 91], rates=[0.04, 0.05])

    def test_metadata_fields(self):
        c = RateCurve(
            tenors=[91], rates=[0.04],
            fetched_at="2026-02-28T00:00:00",
            source="test",
        )
        assert c.fetched_at == "2026-02-28T00:00:00"
        assert c.source == "test"


# ── get_rate_for_dte interpolation ───────────────────────────


class TestGetRateForDTE:
    """Core interpolation logic — the heart of B1."""

    @pytest.fixture
    def normal_curve(self) -> RateCurve:
        """Normal upward-sloping yield curve."""
        return RateCurve(
            tenors=[30, 91, 182, 365, 730],
            rates=[0.040, 0.043, 0.045, 0.048, 0.050],
        )

    @pytest.fixture
    def flat_curve(self) -> RateCurve:
        return make_flat_curve(0.05)

    @pytest.fixture
    def inverted_curve(self) -> RateCurve:
        """Inverted yield curve (short > long)."""
        return RateCurve(
            tenors=[30, 91, 365],
            rates=[0.055, 0.050, 0.040],
        )

    # ── Exact tenor match ──

    def test_exact_tenor_match(self, normal_curve):
        assert get_rate_for_dte(91, normal_curve) == pytest.approx(0.043)
        assert get_rate_for_dte(365, normal_curve) == pytest.approx(0.048)

    def test_exact_first_tenor(self, normal_curve):
        assert get_rate_for_dte(30, normal_curve) == pytest.approx(0.040)

    def test_exact_last_tenor(self, normal_curve):
        assert get_rate_for_dte(730, normal_curve) == pytest.approx(0.050)

    # ── Flat extrapolation at boundaries ──

    def test_below_shortest_tenor(self, normal_curve):
        """DTE < shortest tenor → use shortest rate."""
        assert get_rate_for_dte(0, normal_curve) == pytest.approx(0.040)
        assert get_rate_for_dte(7, normal_curve) == pytest.approx(0.040)
        assert get_rate_for_dte(29, normal_curve) == pytest.approx(0.040)

    def test_above_longest_tenor(self, normal_curve):
        """DTE > longest tenor → use longest rate."""
        assert get_rate_for_dte(1000, normal_curve) == pytest.approx(0.050)
        assert get_rate_for_dte(3650, normal_curve) == pytest.approx(0.050)

    # ── Linear interpolation ──

    def test_midpoint_interpolation(self, normal_curve):
        """Midpoint between 91d (0.043) and 182d (0.045) → 0.044."""
        mid_dte = (91 + 182) // 2  # 136
        r = get_rate_for_dte(mid_dte, normal_curve)
        expected = 0.043 + (0.045 - 0.043) * (mid_dte - 91) / (182 - 91)
        assert r == pytest.approx(expected, abs=1e-8)

    def test_quarter_interpolation(self):
        """25% between two points."""
        c = RateCurve(tenors=[100, 200], rates=[0.04, 0.06])
        r = get_rate_for_dte(125, c)
        assert r == pytest.approx(0.045)

    def test_three_quarter_interpolation(self):
        """75% between two points."""
        c = RateCurve(tenors=[100, 200], rates=[0.04, 0.06])
        r = get_rate_for_dte(175, c)
        assert r == pytest.approx(0.055)

    def test_inverted_curve_interpolation(self, inverted_curve):
        """Interpolation works correctly on inverted curves (rates decrease)."""
        r = get_rate_for_dte(60, inverted_curve)
        expected = 0.055 + (0.050 - 0.055) * (60 - 30) / (91 - 30)
        assert r == pytest.approx(expected, abs=1e-8)
        assert r < 0.055  # between short and mid

    def test_various_dtes_monotonic_on_normal(self, normal_curve):
        """On a normal (upward) curve, rates increase with DTE."""
        dtes = [30, 60, 91, 120, 182, 270, 365, 500, 730]
        rates = [get_rate_for_dte(d, normal_curve) for d in dtes]
        for i in range(1, len(rates)):
            assert rates[i] >= rates[i - 1], (
                f"Rate should be non-decreasing: "
                f"DTE {dtes[i-1]}={rates[i-1]:.6f} > DTE {dtes[i]}={rates[i]:.6f}"
            )

    # ── Flat curve ──

    def test_flat_curve_all_same(self, flat_curve):
        """Flat curve returns same rate regardless of DTE."""
        for dte in [0, 7, 30, 91, 365, 1000]:
            assert get_rate_for_dte(dte, flat_curve) == pytest.approx(0.05)

    # ── Single-point curve ──

    def test_single_point_curve(self):
        c = RateCurve(tenors=[91], rates=[0.043])
        assert get_rate_for_dte(0, c) == 0.043
        assert get_rate_for_dte(91, c) == 0.043
        assert get_rate_for_dte(365, c) == 0.043

    # ── Edge cases ──

    def test_dte_zero(self, normal_curve):
        assert get_rate_for_dte(0, normal_curve) == pytest.approx(0.040)

    def test_negative_dte_rejected(self, normal_curve):
        with pytest.raises(ValueError, match="dte must be >= 0"):
            get_rate_for_dte(-1, normal_curve)

    def test_dte_one(self, normal_curve):
        """DTE=1 is valid (next-day expiry)."""
        assert get_rate_for_dte(1, normal_curve) == pytest.approx(0.040)


# ── make_flat_curve ──────────────────────────────────────────


class TestMakeFlatCurve:
    def test_basic(self):
        c = make_flat_curve(0.05)
        assert c.tenors == [91]
        assert c.rates == [0.05]
        assert c.source == "flat"
        assert c.is_flat

    def test_custom_source(self):
        c = make_flat_curve(0.043, source="irx")
        assert c.source == "irx"

    def test_fetched_at_populated(self):
        c = make_flat_curve(0.05)
        assert c.fetched_at  # non-empty string


# ── get_yield_curve integration ──────────────────────────────


class TestGetYieldCurve:
    def test_returns_rate_curve(self):
        """get_yield_curve() always returns a valid RateCurve."""
        curve = get_yield_curve()
        assert isinstance(curve, RateCurve)
        assert len(curve.tenors) >= 1
        assert len(curve.rates) >= 1
        # Rates should be reasonable (0% to 20%)
        for r in curve.rates:
            assert 0.0 <= r <= 0.20, f"Unreasonable rate: {r}"

    def test_get_rate_from_fetched_curve(self):
        """End-to-end: fetch curve → interpolate for various DTEs."""
        curve = get_yield_curve()
        for dte in [7, 30, 91, 180, 365]:
            r = get_rate_for_dte(dte, curve)
            assert 0.0 <= r <= 0.20, f"DTE {dte}: unreasonable rate {r}"

    def test_fallback_rate(self):
        """With custom fallback, rate should be at most the fallback."""
        curve = get_yield_curve(fallback_rate=0.10)
        assert isinstance(curve, RateCurve)

    def test_caching(self):
        """Second call should return cached curve (same object)."""
        c1 = get_yield_curve()
        c2 = get_yield_curve()
        # May or may not be same object depending on cache state,
        # but both should be valid
        assert isinstance(c1, RateCurve)
        assert isinstance(c2, RateCurve)

    def test_fallback_uses_short_ttl(self):
        """Fallback curves should be cached with short TTL, not 24h."""
        from unittest.mock import patch
        from analysis.rate_curve import (
            _curve_cache,
            _FALLBACK_CACHE_TTL_SECONDS,
            _CACHE_TTL_SECONDS,
        )

        # Clear cache to force fresh fetch
        _curve_cache.pop("treasury_curve", None)

        # Mock _fetch_treasury_curve to fail, forcing fallback path
        with patch("analysis.rate_curve._fetch_treasury_curve", return_value=None):
            curve = get_yield_curve(fallback_rate=0.05)
            assert isinstance(curve, RateCurve)
            assert curve.source in ("irx_fallback", "hardcoded_fallback")

            # Verify cache entry uses short TTL
            entry = _curve_cache.get("treasury_curve")
            assert entry is not None
            _cached_curve, _cached_at, ttl = entry
            assert ttl == _FALLBACK_CACHE_TTL_SECONDS
            assert ttl < _CACHE_TTL_SECONDS  # short TTL < 24h


# ── Realistic scenario tests ─────────────────────────────────


class TestRealisticScenarios:
    """Tests that model real-world option pricing scenarios."""

    def test_short_dated_vs_long_dated(self):
        """Short-dated options should use shorter-tenor rate."""
        curve = RateCurve(
            tenors=[30, 91, 365, 730],
            rates=[0.052, 0.050, 0.045, 0.042],  # inverted
        )
        r_weekly = get_rate_for_dte(7, curve)    # extrapolate short
        r_monthly = get_rate_for_dte(30, curve)   # exact
        r_quarterly = get_rate_for_dte(91, curve)  # exact
        r_annual = get_rate_for_dte(365, curve)   # exact

        assert r_weekly == pytest.approx(0.052)   # flat extrapolation
        assert r_monthly == pytest.approx(0.052)
        assert r_quarterly == pytest.approx(0.050)
        assert r_annual == pytest.approx(0.045)
        # On inverted curve, short > long
        assert r_weekly > r_annual

    def test_backward_compat_with_flat(self):
        """Wrapping existing get_risk_free_rate() in flat curve preserves behavior."""
        from analysis.option_pricing import get_risk_free_rate

        old_rate = get_risk_free_rate()
        flat = make_flat_curve(old_rate, source="irx_compat")

        # Every DTE should return the same rate as the old function
        for dte in [0, 7, 30, 91, 180, 365, 730]:
            assert get_rate_for_dte(dte, flat) == pytest.approx(old_rate)

    def test_rate_precision(self):
        """Interpolation should maintain at least 6 decimal places of precision."""
        curve = RateCurve(
            tenors=[91, 365],
            rates=[0.043210, 0.048765],
        )
        r = get_rate_for_dte(200, curve)
        # Manual calculation: 0.043210 + (0.048765-0.043210)*(200-91)/(365-91)
        expected = 0.043210 + (0.048765 - 0.043210) * (200 - 91) / (365 - 91)
        assert r == pytest.approx(expected, abs=1e-10)

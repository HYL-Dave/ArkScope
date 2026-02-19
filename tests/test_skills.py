"""
Tests for the Skills system (Phase 13).

Verifies skill definitions, template expansion, command parsing, and listing.
"""

import pytest

from src.agents.shared.skills import (
    SKILL_REGISTRY,
    SkillDefinition,
    expand_skill,
    list_skills,
    parse_skill_command,
)


# ============================================================
# Skill Registry Tests
# ============================================================

class TestSkillRegistry:
    def test_registry_has_4_skills(self):
        assert len(SKILL_REGISTRY) == 4

    def test_expected_skill_names(self):
        assert set(SKILL_REGISTRY.keys()) == {
            "full_analysis",
            "portfolio_scan",
            "earnings_prep",
            "sector_rotation",
        }

    def test_all_skills_have_required_fields(self):
        for name, skill in SKILL_REGISTRY.items():
            assert skill.name == name
            assert skill.description
            assert skill.prompt_template
            assert isinstance(skill.required_params, list)
            assert isinstance(skill.aliases, list)
            assert len(skill.aliases) >= 1, f"{name} should have at least one alias"

    def test_full_analysis_requires_ticker(self):
        assert SKILL_REGISTRY["full_analysis"].required_params == ["ticker"]

    def test_portfolio_scan_no_required_params(self):
        assert SKILL_REGISTRY["portfolio_scan"].required_params == []

    def test_earnings_prep_requires_ticker(self):
        assert SKILL_REGISTRY["earnings_prep"].required_params == ["ticker"]

    def test_sector_rotation_no_required_params(self):
        assert SKILL_REGISTRY["sector_rotation"].required_params == []

    def test_no_duplicate_aliases(self):
        all_aliases = []
        for skill in SKILL_REGISTRY.values():
            all_aliases.extend(skill.aliases)
        assert len(all_aliases) == len(set(all_aliases)), "Duplicate aliases found"


# ============================================================
# Expand Skill Tests
# ============================================================

class TestExpandSkill:
    def test_expand_full_analysis(self):
        result = expand_skill("full_analysis", {"ticker": "NVDA"})
        assert result is not None
        assert "NVDA" in result
        assert "entry analysis" in result.lower() or "analysis" in result.lower()

    def test_expand_portfolio_scan_no_params(self):
        result = expand_skill("portfolio_scan", {})
        assert result is not None
        assert "watchlist" in result.lower()

    def test_expand_earnings_prep(self):
        result = expand_skill("earnings_prep", {"ticker": "TSLA"})
        assert result is not None
        assert "TSLA" in result

    def test_expand_sector_rotation(self):
        result = expand_skill("sector_rotation", {})
        assert result is not None
        assert "sector" in result.lower()

    def test_expand_with_missing_param_returns_none(self):
        result = expand_skill("full_analysis", {})
        assert result is None

    def test_expand_with_empty_param_returns_none(self):
        result = expand_skill("full_analysis", {"ticker": ""})
        assert result is None

    def test_expand_unknown_skill_returns_none(self):
        result = expand_skill("nonexistent_skill", {})
        assert result is None

    def test_expand_by_alias(self):
        result = expand_skill("fa", {"ticker": "AAPL"})
        assert result is not None
        assert "AAPL" in result

    def test_expand_by_alias_scan(self):
        result = expand_skill("scan", {})
        assert result is not None

    def test_ticker_substitution_all_occurrences(self):
        result = expand_skill("full_analysis", {"ticker": "AFRM"})
        assert result is not None
        assert result.count("AFRM") >= 2  # ticker appears multiple times


# ============================================================
# Parse Skill Command Tests
# ============================================================

class TestParseSkillCommand:
    def test_parse_name_and_ticker(self):
        name, params = parse_skill_command("full_analysis NVDA")
        assert name == "full_analysis"
        assert params == {"ticker": "NVDA"}

    def test_parse_alias_and_ticker(self):
        name, params = parse_skill_command("fa aapl")
        assert name == "full_analysis"
        assert params == {"ticker": "AAPL"}  # uppercased

    def test_parse_name_only_no_params(self):
        name, params = parse_skill_command("portfolio_scan")
        assert name == "portfolio_scan"
        assert params == {}

    def test_parse_alias_only(self):
        name, params = parse_skill_command("scan")
        assert name == "portfolio_scan"

    def test_parse_empty_string(self):
        name, params = parse_skill_command("")
        assert name is None
        assert params == {}

    def test_parse_unknown_name(self):
        name, params = parse_skill_command("unknown_skill")
        assert name == "unknown_skill"  # unresolved, returned for error message
        assert params == {}

    def test_parse_earnings_prep_alias(self):
        name, params = parse_skill_command("ep TSLA")
        assert name == "earnings_prep"
        assert params == {"ticker": "TSLA"}

    def test_parse_sector_rotation_alias(self):
        name, params = parse_skill_command("sr")
        assert name == "sector_rotation"


# ============================================================
# List Skills Tests
# ============================================================

class TestListSkills:
    def test_returns_all_skills(self):
        skills = list_skills()
        assert len(skills) == 4

    def test_skill_info_structure(self):
        skills = list_skills()
        for s in skills:
            assert "name" in s
            assert "description" in s
            assert "required_params" in s
            assert "aliases" in s
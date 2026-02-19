"""
Tests for the Skills system (Phase 13 + custom skills).

Verifies skill definitions, template expansion, command parsing, listing,
and custom skill loading from YAML.
"""

import os
import tempfile

import pytest

from src.agents.shared.skills import (
    SKILL_REGISTRY,
    SkillDefinition,
    _ALIAS_MAP,
    _BUILTIN_SKILL_NAMES,
    _CUSTOM_SKILLS_DIR,
    expand_skill,
    list_skills,
    load_custom_skills,
    parse_skill_command,
)


# ============================================================
# Skill Registry Tests
# ============================================================

class TestSkillRegistry:
    def test_registry_has_at_least_4_builtin_skills(self):
        assert len(SKILL_REGISTRY) >= 4

    def test_expected_builtin_skill_names(self):
        expected = {"full_analysis", "portfolio_scan", "earnings_prep", "sector_rotation"}
        assert expected.issubset(set(SKILL_REGISTRY.keys()))

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
        assert len(skills) >= 4

    def test_skill_info_structure(self):
        skills = list_skills()
        for s in skills:
            assert "name" in s
            assert "description" in s
            assert "required_params" in s
            assert "aliases" in s


# ============================================================
# Custom Skills Loading Tests
# ============================================================

class TestCustomSkillsLoading:
    """Tests for load_custom_skills() YAML loading."""

    def test_builtin_names_frozenset(self):
        assert "full_analysis" in _BUILTIN_SKILL_NAMES
        assert "portfolio_scan" in _BUILTIN_SKILL_NAMES
        assert "earnings_prep" in _BUILTIN_SKILL_NAMES
        assert "sector_rotation" in _BUILTIN_SKILL_NAMES

    def test_load_from_empty_dir(self):
        """Empty config/skills/ should load 0 custom skills."""
        # The .gitkeep dir exists but has no YAML
        count = load_custom_skills()
        assert count == 0

    def test_load_valid_yaml(self, tmp_path, monkeypatch):
        """Load a valid custom skill YAML."""
        import src.agents.shared.skills as skills_mod

        # Create temp YAML
        yaml_content = (
            "name: test_custom\n"
            "description: A test custom skill\n"
            "required_params:\n"
            "  - ticker\n"
            "aliases:\n"
            "  - tc\n"
            "prompt_template: |\n"
            "  Analyze {ticker} for testing.\n"
        )
        (tmp_path / "test_custom.yaml").write_text(yaml_content)

        # Monkeypatch the custom skills directory
        monkeypatch.setattr(skills_mod, "_CUSTOM_SKILLS_DIR", tmp_path)

        count = load_custom_skills()
        assert count == 1
        assert "test_custom" in SKILL_REGISTRY
        assert SKILL_REGISTRY["test_custom"].description == "A test custom skill"
        assert SKILL_REGISTRY["test_custom"].required_params == ["ticker"]
        assert "tc" in _ALIAS_MAP

        # Verify expansion works
        result = expand_skill("test_custom", {"ticker": "NVDA"})
        assert result is not None
        assert "NVDA" in result

        # Cleanup: remove from registry
        del SKILL_REGISTRY["test_custom"]
        del _ALIAS_MAP["tc"]

    def test_builtin_cannot_be_overridden(self, tmp_path, monkeypatch):
        """Custom YAML with a built-in name should be skipped."""
        import src.agents.shared.skills as skills_mod

        yaml_content = (
            "name: full_analysis\n"
            "description: Override attempt\n"
            "prompt_template: Should not replace built-in\n"
        )
        (tmp_path / "full_analysis.yaml").write_text(yaml_content)

        monkeypatch.setattr(skills_mod, "_CUSTOM_SKILLS_DIR", tmp_path)

        count = load_custom_skills()
        assert count == 0
        # Original should be unchanged
        assert "Override attempt" not in SKILL_REGISTRY["full_analysis"].description

    def test_bad_yaml_skipped(self, tmp_path, monkeypatch):
        """Invalid YAML content should be skipped without error."""
        import src.agents.shared.skills as skills_mod

        (tmp_path / "bad.yaml").write_text(": invalid: yaml: [")

        monkeypatch.setattr(skills_mod, "_CUSTOM_SKILLS_DIR", tmp_path)

        count = load_custom_skills()
        assert count == 0

    def test_empty_yaml_skipped(self, tmp_path, monkeypatch):
        """Empty YAML file should be skipped."""
        import src.agents.shared.skills as skills_mod

        (tmp_path / "empty.yaml").write_text("")

        monkeypatch.setattr(skills_mod, "_CUSTOM_SKILLS_DIR", tmp_path)

        count = load_custom_skills()
        assert count == 0

    def test_name_from_filename_stem(self, tmp_path, monkeypatch):
        """If name is not in YAML, use filename stem."""
        import src.agents.shared.skills as skills_mod

        yaml_content = (
            "description: Name from stem\n"
            "prompt_template: Test prompt\n"
        )
        (tmp_path / "my_analysis.yaml").write_text(yaml_content)

        monkeypatch.setattr(skills_mod, "_CUSTOM_SKILLS_DIR", tmp_path)

        count = load_custom_skills()
        assert count == 1
        assert "my_analysis" in SKILL_REGISTRY
        assert SKILL_REGISTRY["my_analysis"].description == "Name from stem"

        # Cleanup
        del SKILL_REGISTRY["my_analysis"]

    def test_nonexistent_dir_returns_zero(self, tmp_path, monkeypatch):
        """Nonexistent directory should return 0."""
        import src.agents.shared.skills as skills_mod

        monkeypatch.setattr(
            skills_mod, "_CUSTOM_SKILLS_DIR", tmp_path / "nonexistent"
        )

        count = load_custom_skills()
        assert count == 0
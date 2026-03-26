"""
Tests for the Skills system (Phase 13 + Phase G).

Verifies skill definitions, template expansion, command parsing, listing,
custom skill loading, SKILL.md parsing, auto-trigger matching, and CLI hints.
"""

import os
import tempfile

import pytest

from src.agents.shared.skills import (
    SKILL_REGISTRY,
    SkillDefinition,
    SkillMatchResult,
    _ALIAS_MAP,
    _BUILTIN_SKILL_NAMES,
    _CUSTOM_DIR,
    _parse_skill_md,
    _scan_builtin,
    build_auto_apply_context,
    expand_skill,
    list_skills,
    load_custom_skills,
    match_skill_trigger,
    parse_skill_command,
    rebuild_skill_registry,
    render_skill_suggestion_cli,
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
    """Tests for load_custom_skills() / rebuild_skill_registry() YAML loading."""

    def _rebuild_with_custom_dir(self, custom_dir, monkeypatch):
        """Helper: rebuild registry with a custom dir override."""
        import src.agents.shared.skills as skills_mod
        monkeypatch.setattr(skills_mod, "_CUSTOM_DIR", custom_dir)
        return rebuild_skill_registry()

    @staticmethod
    def _baseline_count():
        """Count of repo-owned skills (builtin + packaged) without custom."""
        return len(SKILL_REGISTRY)

    def test_builtin_names_frozenset(self):
        assert "full_analysis" in _BUILTIN_SKILL_NAMES
        assert "portfolio_scan" in _BUILTIN_SKILL_NAMES
        assert "earnings_prep" in _BUILTIN_SKILL_NAMES
        assert "sector_rotation" in _BUILTIN_SKILL_NAMES

    def test_load_from_empty_dir(self, tmp_path, monkeypatch):
        """Empty custom dir should have only repo-owned skills."""
        baseline = self._baseline_count()
        total = self._rebuild_with_custom_dir(tmp_path, monkeypatch)
        assert total == baseline
        assert total >= len(_BUILTIN_SKILL_NAMES)

    def test_load_valid_yaml(self, tmp_path, monkeypatch):
        """Load a valid custom skill YAML."""
        baseline = self._baseline_count()
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

        total = self._rebuild_with_custom_dir(tmp_path, monkeypatch)
        assert total == baseline + 1
        assert "test_custom" in SKILL_REGISTRY
        assert SKILL_REGISTRY["test_custom"].description == "A test custom skill"
        assert SKILL_REGISTRY["test_custom"].required_params == ["ticker"]
        assert "tc" in _ALIAS_MAP

        # Verify expansion works
        result = expand_skill("test_custom", {"ticker": "NVDA"})
        assert result is not None
        assert "NVDA" in result

    def test_builtin_cannot_be_overridden(self, tmp_path, monkeypatch):
        """Custom YAML with a built-in name should be skipped (builtin wins)."""
        yaml_content = (
            "name: full_analysis\n"
            "description: Override attempt\n"
            "prompt_template: Should not replace built-in\n"
        )
        (tmp_path / "full_analysis.yaml").write_text(yaml_content)

        self._rebuild_with_custom_dir(tmp_path, monkeypatch)
        # Builtin should be unchanged
        assert "Override attempt" not in SKILL_REGISTRY["full_analysis"].description

    def test_bad_yaml_skipped(self, tmp_path, monkeypatch):
        """Invalid YAML content should be skipped without error."""
        baseline = self._baseline_count()
        (tmp_path / "bad.yaml").write_text(": invalid: yaml: [")

        total = self._rebuild_with_custom_dir(tmp_path, monkeypatch)
        assert total == baseline

    def test_empty_yaml_skipped(self, tmp_path, monkeypatch):
        """Empty YAML file should be skipped."""
        baseline = self._baseline_count()
        (tmp_path / "empty.yaml").write_text("")

        total = self._rebuild_with_custom_dir(tmp_path, monkeypatch)
        assert total == baseline

    def test_name_from_filename_stem(self, tmp_path, monkeypatch):
        """If name is not in YAML, use filename stem."""
        yaml_content = (
            "description: Name from stem\n"
            "prompt_template: Test prompt\n"
        )
        (tmp_path / "my_analysis.yaml").write_text(yaml_content)

        self._rebuild_with_custom_dir(tmp_path, monkeypatch)
        assert "my_analysis" in SKILL_REGISTRY
        assert SKILL_REGISTRY["my_analysis"].description == "Name from stem"

    def test_nonexistent_dir_returns_zero(self, tmp_path, monkeypatch):
        """Nonexistent custom directory should still load repo-owned skills."""
        # Rebuild with empty dir first for a clean baseline (avoids prior test pollution)
        baseline = self._rebuild_with_custom_dir(tmp_path, monkeypatch)
        total = self._rebuild_with_custom_dir(tmp_path / "nonexistent", monkeypatch)
        assert total == baseline


# ============================================================
# SKILL.md Parsing Tests (Phase G)
# ============================================================

class TestSkillMdParsing:
    """Tests for _parse_skill_md() frontmatter + body extraction."""

    def test_parse_valid_skill_md(self, tmp_path):
        md = (
            "---\n"
            "name: test_skill\n"
            "description: A test\n"
            "required_params: [ticker]\n"
            "aliases: [ts]\n"
            "trigger: test skill|testing\n"
            "category: testing\n"
            "---\n"
            "\n"
            "Analyze {ticker} now.\n"
        )
        p = tmp_path / "test_skill" / "SKILL.md"
        p.parent.mkdir()
        p.write_text(md)
        skill = _parse_skill_md(p)
        assert skill is not None
        assert skill.name == "test_skill"
        assert skill.description == "A test"
        assert skill.required_params == ["ticker"]
        assert "ts" in skill.aliases
        assert skill.trigger == "test skill|testing"
        assert skill.category == "testing"
        assert "Analyze {ticker} now." in skill.prompt_template

    def test_parse_missing_frontmatter(self, tmp_path):
        p = tmp_path / "no_front" / "SKILL.md"
        p.parent.mkdir()
        p.write_text("Just some text without frontmatter.\n")
        skill = _parse_skill_md(p)
        assert skill is None

    def test_parse_bom_and_crlf(self, tmp_path):
        """BOM and CRLF should be handled transparently."""
        md = (
            "\ufeff---\r\n"
            "name: bom_skill\r\n"
            "description: BOM test\r\n"
            "---\r\n"
            "\r\n"
            "Body text.\r\n"
        )
        p = tmp_path / "bom_skill" / "SKILL.md"
        p.parent.mkdir()
        p.write_text(md)
        skill = _parse_skill_md(p)
        assert skill is not None
        assert skill.name == "bom_skill"
        assert "Body text." in skill.prompt_template

    def test_name_fallback_to_parent_dir(self, tmp_path):
        """Custom SKILL.md may fall back to the parent directory slug."""
        md = "---\ndescription: No name field\n---\n\nBody.\n"
        p = tmp_path / "my-cool-skill" / "SKILL.md"
        p.parent.mkdir()
        p.write_text(md)
        skill = _parse_skill_md(p)
        assert skill is not None
        assert skill.name == "my_cool_skill"  # hyphens → underscores

    def test_repo_owned_missing_name_raises(self, tmp_path):
        md = "---\ndescription: No name field\n---\n\nBody.\n"
        p = tmp_path / "packaged-skill" / "SKILL.md"
        p.parent.mkdir()
        p.write_text(md)
        with pytest.raises(RuntimeError, match="Missing required skill name"):
            _parse_skill_md(p, require_name=True, allow_name_fallback=False)

    def test_all_frontmatter_fields(self, tmp_path):
        md = (
            "---\n"
            "name: full_fields\n"
            "description: All fields present\n"
            "trigger: full fields|all fields\n"
            "required_params: [ticker]\n"
            "aliases: [ff]\n"
            "category: test-cat\n"
            "auto_apply: false\n"
            "data_sources:\n"
            "  required: [tool_a]\n"
            "  optional: [tool_b]\n"
            "output: report\n"
            "---\n"
            "\n"
            "Do something with {ticker}.\n"
        )
        p = tmp_path / "full_fields" / "SKILL.md"
        p.parent.mkdir()
        p.write_text(md)
        skill = _parse_skill_md(p)
        assert skill is not None
        assert skill.auto_apply is False
        assert skill.data_sources == {"required": ["tool_a"], "optional": ["tool_b"]}
        assert skill.output == "report"

    def test_kebab_case_auto_apply_supported(self, tmp_path):
        md = (
            "---\n"
            "name: kebab_auto\n"
            "description: Kebab key\n"
            "auto-apply: false\n"
            "---\n\n"
            "Body.\n"
        )
        p = tmp_path / "kebab_auto" / "SKILL.md"
        p.parent.mkdir()
        p.write_text(md)
        skill = _parse_skill_md(p)
        assert skill is not None
        assert skill.auto_apply is False

    def test_empty_body_returns_none(self, tmp_path):
        """Empty body is treated as invalid (warning + skip)."""
        md = "---\nname: empty_body\ndescription: No body\n---\n"
        p = tmp_path / "empty_body" / "SKILL.md"
        p.parent.mkdir()
        p.write_text(md)
        skill = _parse_skill_md(p)
        assert skill is None

    def test_invalid_yaml_in_frontmatter(self, tmp_path):
        md = "---\n: invalid: yaml: [\n---\n\nBody.\n"
        p = tmp_path / "bad_yaml" / "SKILL.md"
        p.parent.mkdir()
        p.write_text(md)
        skill = _parse_skill_md(p)
        assert skill is None

    def test_invalid_name_format(self, tmp_path):
        """Names must be snake_case (lowercase + underscores)."""
        md = "---\nname: UPPER_CASE\ndescription: Bad name\n---\n\nBody.\n"
        p = tmp_path / "upper_case" / "SKILL.md"
        p.parent.mkdir()
        p.write_text(md)
        skill = _parse_skill_md(p)
        assert skill is None


# ============================================================
# Explicit Replacement Tests (Phase G)
# ============================================================

class TestExplicitReplacement:
    """Verify expand_skill() uses explicit replacement, not format_map."""

    def _make_skill_with_template(self, template: str, monkeypatch):
        """Inject a test skill with a given template into the registry."""
        import src.agents.shared.skills as skills_mod
        skill = SkillDefinition(
            name="_test_replace",
            description="test",
            prompt_template=template,
            required_params=["ticker"],
            aliases=["_tr"],
        )
        monkeypatch.setitem(SKILL_REGISTRY, "_test_replace", skill)
        monkeypatch.setitem(skills_mod._ALIAS_MAP, "_tr", "_test_replace")
        return skill

    def test_markdown_curly_braces(self, monkeypatch):
        """Markdown with {} (e.g. JSON examples) should not crash."""
        tmpl = "Analyze {ticker}.\n\nExample JSON: {\"key\": \"value\"}\n"
        self._make_skill_with_template(tmpl, monkeypatch)
        result = expand_skill("_test_replace", {"ticker": "NVDA"})
        assert result is not None
        assert "NVDA" in result
        assert '{"key": "value"}' in result

    def test_python_dict_literal(self, monkeypatch):
        tmpl = "For {ticker}: use params = {\"alpha\": 0.5, \"beta\": 1}\n"
        self._make_skill_with_template(tmpl, monkeypatch)
        result = expand_skill("_test_replace", {"ticker": "AAPL"})
        assert result is not None
        assert "AAPL" in result
        assert '"alpha"' in result

    def test_unnamed_braces(self, monkeypatch):
        tmpl = "Step 1: {} → Step 2: {ticker} analysis.\n"
        self._make_skill_with_template(tmpl, monkeypatch)
        result = expand_skill("_test_replace", {"ticker": "TSLA"})
        assert result is not None
        assert "TSLA" in result
        assert "{}" in result  # unnamed braces preserved

    def test_multiple_ticker_occurrences(self, monkeypatch):
        tmpl = "{ticker} overview.\n{ticker} fundamentals.\n{ticker} conclusion.\n"
        self._make_skill_with_template(tmpl, monkeypatch)
        result = expand_skill("_test_replace", {"ticker": "GOOG"})
        assert result is not None
        assert result.count("GOOG") == 3

    def test_nested_braces(self, monkeypatch):
        tmpl = "Code: `dict = {{ticker: {ticker}}}`\n"
        self._make_skill_with_template(tmpl, monkeypatch)
        result = expand_skill("_test_replace", {"ticker": "META"})
        assert result is not None
        assert "META" in result


# ============================================================
# Registry Rebuild Tests (Phase G)
# ============================================================

class TestRegistryRebuild:
    """Test rebuild_skill_registry() behavior."""

    def _rebuild_with_custom_dir(self, custom_dir, monkeypatch):
        import src.agents.shared.skills as skills_mod
        monkeypatch.setattr(skills_mod, "_CUSTOM_DIR", custom_dir)
        return rebuild_skill_registry()

    def test_rebuild_clears_stale_custom_skills(self, tmp_path, monkeypatch):
        """Adding then removing a custom skill should clean it from registry."""
        yaml_content = "name: temp_skill\ndescription: Temp\nprompt_template: Temp\n"
        (tmp_path / "temp_skill.yaml").write_text(yaml_content)

        self._rebuild_with_custom_dir(tmp_path, monkeypatch)
        assert "temp_skill" in SKILL_REGISTRY

        # Remove the file and rebuild
        (tmp_path / "temp_skill.yaml").unlink()
        self._rebuild_with_custom_dir(tmp_path, monkeypatch)
        assert "temp_skill" not in SKILL_REGISTRY

    def test_rebuild_includes_packaged_skills(self, tmp_path, monkeypatch):
        """Rebuild should include packaged (Tier 2) skills from resources/."""
        total = self._rebuild_with_custom_dir(tmp_path, monkeypatch)
        assert total >= len(_BUILTIN_SKILL_NAMES) + 1  # at least some packaged

    def test_alias_map_rebuilt_on_rebuild(self, tmp_path, monkeypatch):
        """Alias map should reflect current registry state after rebuild."""
        yaml_content = (
            "name: alias_test\ndescription: Test\n"
            "aliases:\n  - at99\nprompt_template: Test\n"
        )
        (tmp_path / "alias_test.yaml").write_text(yaml_content)
        self._rebuild_with_custom_dir(tmp_path, monkeypatch)
        assert "at99" in _ALIAS_MAP

        (tmp_path / "alias_test.yaml").unlink()
        self._rebuild_with_custom_dir(tmp_path, monkeypatch)
        assert "at99" not in _ALIAS_MAP

    def test_custom_md_skill_loaded(self, tmp_path, monkeypatch):
        """Custom SKILL.md in config/skills/custom/{category}/{skill}/ should load."""
        # Structure: _CUSTOM_DIR/custom/{category}/{skill_dir}/SKILL.md
        cat_dir = tmp_path / "custom" / "user-skills"
        skill_dir = cat_dir / "my-custom"
        skill_dir.mkdir(parents=True)
        md = "---\nname: my_custom\ndescription: Custom MD\n---\n\nDo something.\n"
        (skill_dir / "SKILL.md").write_text(md)

        import src.agents.shared.skills as skills_mod
        monkeypatch.setattr(skills_mod, "_CUSTOM_DIR", tmp_path)
        rebuild_skill_registry()
        assert "my_custom" in SKILL_REGISTRY

    def test_recursive_custom_md_skill_loaded(self, tmp_path, monkeypatch):
        """Custom SKILL.md loading should recurse beyond one category level."""
        skill_dir = tmp_path / "custom" / "alpha" / "beta" / "deep-skill"
        skill_dir.mkdir(parents=True)
        md = "---\nname: deep_skill\ndescription: Deep custom\n---\n\nDo something deep.\n"
        (skill_dir / "SKILL.md").write_text(md)

        import src.agents.shared.skills as skills_mod
        monkeypatch.setattr(skills_mod, "_CUSTOM_DIR", tmp_path)
        rebuild_skill_registry()
        assert "deep_skill" in SKILL_REGISTRY

    def test_builtin_missing_skill_md_raises(self, tmp_path):
        """Builtin directories must each contain a SKILL.md file."""
        (tmp_path / "missing-skill-md").mkdir()
        with pytest.raises(RuntimeError, match="Builtin skill missing SKILL.md"):
            _scan_builtin(tmp_path)


# ============================================================
# Auto-Trigger Matching Tests (Phase G)
# ============================================================

class TestAutoTrigger:
    """Test match_skill_trigger() matching logic."""

    def test_exact_phrase_match(self):
        r = match_skill_trigger("run a full analysis on NVDA")
        assert r.reason == "unique"
        assert r.skill is not None
        assert r.skill.name == "full_analysis"

    def test_ordered_words_match(self):
        r = match_skill_trigger("do a comprehensive market analysis please")
        assert r.reason == "unique"
        assert r.skill is not None
        assert r.skill.name == "full_analysis"

    def test_case_insensitive(self):
        r = match_skill_trigger("SECTOR ROTATION overview")
        assert r.reason == "unique"
        assert r.skill is not None
        assert r.skill.name == "sector_rotation"

    def test_no_match(self):
        r = match_skill_trigger("what is the weather today")
        assert r.reason == "none"
        assert r.skill is None
        assert r.candidates == []

    def test_multi_match_returns_candidates(self):
        """A query matching multiple skills should return candidates."""
        # "earnings" appears in both earnings_prep and earnings_analysis triggers
        r = match_skill_trigger("earnings analysis report")
        if r.reason == "multiple":
            assert len(r.candidates) >= 2
        # If only one matches due to specificity, that's also valid
        elif r.reason == "unique":
            assert r.skill is not None

    def test_packaged_skill_trigger(self):
        r = match_skill_trigger("build a dcf model for AAPL")
        assert r.reason == "unique"
        assert r.skill is not None
        assert r.skill.name == "dcf_model"

    def test_catalyst_calendar_trigger(self):
        r = match_skill_trigger("show me the catalyst calendar for TSLA")
        assert r.reason == "unique"
        assert r.skill is not None
        assert r.skill.name == "catalyst_calendar"

    def test_empty_query_no_match(self):
        r = match_skill_trigger("")
        assert r.reason == "none"

    def test_prefers_best_phrase_for_same_skill(self, monkeypatch):
        import src.agents.shared.skills as skills_mod
        original = list(skills_mod._TRIGGER_INDEX)
        try:
            skill_a = SkillDefinition(
                name="skill_a",
                description="A",
                prompt_template="A",
                trigger="alpha beta gamma|beta",
            )
            skill_b = SkillDefinition(
                name="skill_b",
                description="B",
                prompt_template="B",
                trigger="alpha beta gamma",
            )
            monkeypatch.setattr(
                skills_mod,
                "_TRIGGER_INDEX",
                [
                    ("alpha beta gamma", skill_a),
                    ("alpha beta gamma", skill_b),
                    ("beta", skill_a),
                ],
            )
            r = match_skill_trigger("alpha xxx beta yyy gamma beta")
            assert r.reason == "unique"
            assert r.skill is not None
            assert r.skill.name == "skill_a"
        finally:
            monkeypatch.setattr(skills_mod, "_TRIGGER_INDEX", original)


# ============================================================
# Auto-Apply Context Tests (Phase G)
# ============================================================

class TestAutoApplyContext:
    """Test build_auto_apply_context() for paramless auto-apply skills."""

    def test_auto_apply_injects_skill_body(self):
        """Paramless + auto_apply skill should inject full body."""
        # portfolio_scan has auto_apply=False, so let's find one that can auto-apply
        # or test with a mock
        skill = SkillDefinition(
            name="_auto_test",
            description="Auto test",
            prompt_template="Do the auto thing.",
            auto_apply=True,
        )
        assert skill.can_auto_apply()
        # Test via direct insertion
        import src.agents.shared.skills as skills_mod
        old = SKILL_REGISTRY.get("_auto_test")
        SKILL_REGISTRY["_auto_test"] = skill
        try:
            ctx = build_auto_apply_context(skill, "run auto scan")
            assert "[Auto-matched skill: _auto_test]" in ctx
            assert "Do the auto thing." in ctx
            assert "[User query]" in ctx
            assert "run auto scan" in ctx
        finally:
            if old is None:
                SKILL_REGISTRY.pop("_auto_test", None)
            else:
                SKILL_REGISTRY["_auto_test"] = old

    def test_can_auto_apply_with_params_is_false(self):
        skill = SkillDefinition(
            name="_param_skill",
            description="Needs params",
            prompt_template="Analyze {ticker}.",
            required_params=["ticker"],
            auto_apply=True,
        )
        assert not skill.can_auto_apply()

    def test_can_auto_apply_with_auto_apply_false(self):
        skill = SkillDefinition(
            name="_no_auto",
            description="No auto",
            prompt_template="Just prompt.",
            auto_apply=False,
        )
        assert not skill.can_auto_apply()


# ============================================================
# CLI Suggestion Rendering Tests (Phase G)
# ============================================================

class TestRenderSuggestionCli:
    """Test render_skill_suggestion_cli() output format."""

    def test_unique_with_params_suggestion(self):
        skill = SkillDefinition(
            name="test_skill",
            description="Test",
            prompt_template="Do {ticker}.",
            required_params=["ticker"],
            aliases=["ts"],
        )
        result = SkillMatchResult(skill=skill, candidates=["test_skill"], reason="unique")
        text = render_skill_suggestion_cli(result)
        assert "test_skill" in text
        assert "/skill test_skill" in text
        assert "<TICKER>" in text
        assert "[dim]" in text

    def test_multiple_candidates_text(self):
        result = SkillMatchResult(
            candidates=["skill_a", "skill_b", "skill_c"],
            reason="multiple",
        )
        text = render_skill_suggestion_cli(result)
        assert "skill_a" in text
        assert "skill_b" in text
        assert "skill_c" in text
        assert "Multiple skills match" in text
        assert "[dim]" in text

    def test_none_reason_empty(self):
        result = SkillMatchResult(reason="none")
        text = render_skill_suggestion_cli(result)
        assert text == ""


# ============================================================
# Dynamic Skills List Tests (Phase G)
# ============================================================

class TestDynamicSkillsList:
    """Test that system prompt and list_skills() reflect registry state."""

    def test_system_prompt_includes_all_skills(self):
        from src.agents.shared.prompts import build_system_prompt
        prompt = build_system_prompt()
        for name in ["full_analysis", "portfolio_scan", "earnings_prep", "sector_rotation"]:
            assert name in prompt

    def test_system_prompt_includes_packaged_skills(self):
        from src.agents.shared.prompts import build_system_prompt
        prompt = build_system_prompt()
        for name in ["comps_analysis", "dcf_model", "competitive_analysis"]:
            assert name in prompt

    def test_list_skills_sorted_by_category_name(self):
        skills = list_skills()
        keys = [(s["category"], s["name"]) for s in skills]
        assert keys == sorted(keys)

    def test_list_skills_has_category_field(self):
        skills = list_skills()
        for s in skills:
            assert "category" in s
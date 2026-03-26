"""
Skills system — predefined goal-oriented analysis workflows.

Phase 13: Basic skills (4 builtin, YAML custom).
Phase G:  Rich SKILL.md format, tiered registry, auto-trigger matching.

Skills are NOT subagents or execution engines. They are structured prompt
injections that define goals, minimum data sources, and output requirements.
The LLM decides tool selection, call order, and analysis strategy on its own.

Usage:
    /skill full_analysis NVDA   → expands to goal-oriented prompt → fed to agent
    /skill portfolio_scan       → no params needed
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

# ── Repo root resolution (from skills.py location) ──────────
_REPO_ROOT = Path(__file__).resolve().parents[3]
_RESOURCES_DIR = _REPO_ROOT / "resources" / "skills"
_CUSTOM_DIR = _REPO_ROOT / "config" / "skills"

# Name validation: snake_case only
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# Frontmatter extraction: --- delimited YAML block at file start
_FRONTMATTER_RE = re.compile(
    r"\A\s*---[ \t]*\n(.*?\n)---[ \t]*\n",
    re.DOTALL,
)


# ── Data classes ─────────────────────────────────────────────

@dataclass
class SkillDefinition:
    """A predefined goal-oriented analysis workflow."""

    name: str
    description: str
    prompt_template: str  # Body content (SKILL.md body or legacy template)
    required_params: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    # --- Phase G additions ---
    trigger: Optional[str] = None       # "comps|comparable|peer comparison"
    category: Optional[str] = None      # "financial-analysis"
    data_sources: Optional[Dict] = None # {"required": [...], "optional": [...]}
    output: Optional[str] = None        # "report" or None
    auto_apply: bool = True             # False → UI suggestion only
    source_path: Optional[str] = None   # SKILL.md path (debug)

    def can_auto_apply(self) -> bool:
        """True only if paramless AND auto_apply enabled."""
        return self.auto_apply and not self.required_params


@dataclass
class SkillMatchResult:
    """Result of trigger matching against a user query."""

    skill: Optional[SkillDefinition] = None
    candidates: List[str] = field(default_factory=list)
    reason: str = "none"  # "none" | "unique" | "multiple"


# ── SKILL.md parser ──────────────────────────────────────────

def _parse_skill_md(path: Path, *, hard_fail: bool = False) -> Optional[SkillDefinition]:
    """Parse a SKILL.md file into a SkillDefinition.

    Args:
        path: Path to SKILL.md file.
        hard_fail: If True, raise on errors (for Tier 1 builtins).
                   If False, log warning and return None.

    Returns:
        SkillDefinition or None on parse failure (when hard_fail=False).
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as e:
        if hard_fail:
            raise RuntimeError(f"Cannot read {path}: {e}") from e
        logger.warning(f"Cannot read {path}: {e}")
        return None

    # BOM + CRLF normalization
    text = raw.lstrip("\ufeff").replace("\r\n", "\n")

    # Extract frontmatter
    m = _FRONTMATTER_RE.match(text)
    if not m:
        msg = f"No valid YAML frontmatter in {path}"
        if hard_fail:
            raise RuntimeError(msg)
        logger.warning(msg)
        return None

    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        msg = f"Invalid YAML frontmatter in {path}: {e}"
        if hard_fail:
            raise RuntimeError(msg)
        logger.warning(msg)
        return None

    if not isinstance(fm, dict):
        msg = f"Frontmatter is not a mapping in {path}"
        if hard_fail:
            raise RuntimeError(msg)
        logger.warning(msg)
        return None

    # Body = everything after frontmatter
    body = text[m.end():].strip()

    # Name resolution
    name = fm.get("name")
    if name is not None:
        name = str(name)
    if not name:
        # Fallback: parent directory slug → snake_case
        name = path.parent.name.replace("-", "_")

    # Validate name
    if not _NAME_RE.match(name):
        msg = f"Invalid skill name '{name}' in {path} (must be snake_case)"
        if hard_fail:
            raise RuntimeError(msg)
        logger.warning(msg)
        return None

    # auto_apply: accept both snake_case and kebab-case keys
    auto_apply_val = fm.get("auto_apply", fm.get("auto-apply", True))

    # Guard: paramless skill with short trigger phrases → force auto_apply=False
    required_params = fm.get("required_params", []) or []
    trigger_str = fm.get("trigger")
    if auto_apply_val and not required_params and trigger_str:
        phrases = [p.strip() for p in str(trigger_str).split("|") if p.strip()]
        for phrase in phrases:
            if len(phrase.split()) < 2:
                logger.warning(
                    f"Skill '{name}' has single-word trigger '{phrase}' with no "
                    f"required_params — auto_apply forced to False"
                )
                auto_apply_val = False
                break

    skill = SkillDefinition(
        name=name,
        description=str(fm.get("description", "")),
        prompt_template=body,
        required_params=required_params,
        aliases=fm.get("aliases", []) or [],
        trigger=str(trigger_str) if trigger_str else None,
        category=fm.get("category"),
        data_sources=fm.get("data_sources"),
        output=fm.get("output"),
        auto_apply=bool(auto_apply_val),
        source_path=str(path),
    )

    if not skill.prompt_template:
        msg = f"Empty body in {path}"
        if hard_fail:
            raise RuntimeError(msg)
        logger.warning(msg)
        return None

    return skill


# ── Skill registry (populated by rebuild) ────────────────────

SKILL_REGISTRY: Dict[str, SkillDefinition] = {}
_ALIAS_MAP: Dict[str, str] = {}
_TRIGGER_INDEX: List[Tuple[str, SkillDefinition]] = []

# Built-in skill names (canonical list)
_BUILTIN_SKILL_NAMES = frozenset({
    "full_analysis", "portfolio_scan", "earnings_prep", "sector_rotation",
})


# ── Tiered scanning helpers ──────────────────────────────────

def _scan_builtin(builtin_dir: Path) -> Dict[str, SkillDefinition]:
    """Scan Tier 1: resources/skills/builtin/**/SKILL.md.

    Hard failure on missing directory or broken files.
    """
    if not builtin_dir.exists():
        raise RuntimeError(
            f"Builtin skills directory missing: {builtin_dir}"
        )

    results: Dict[str, SkillDefinition] = {}
    for skill_dir in sorted(builtin_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue
        skill = _parse_skill_md(skill_file, hard_fail=True)
        assert skill is not None  # hard_fail=True guarantees this
        if skill.name in results:
            raise RuntimeError(
                f"Duplicate builtin skill name '{skill.name}': "
                f"{results[skill.name].source_path} vs {skill.source_path}"
            )
        results[skill.name] = skill

    if not results:
        raise RuntimeError(f"No builtin skills found in {builtin_dir}")

    return results


def _scan_dir(base_dir: Path, *, exclude: Optional[List[str]] = None) -> Dict[str, SkillDefinition]:
    """Scan Tier 2/3a: resources/skills/{category}/**/SKILL.md or config/skills/custom/**/SKILL.md.

    Warning + skip on errors. First-wins within same tier.
    """
    results: Dict[str, SkillDefinition] = {}
    exclude = set(exclude or [])

    if not base_dir.exists():
        return results

    for category_dir in sorted(base_dir.iterdir()):
        if not category_dir.is_dir() or category_dir.name in exclude:
            continue
        for skill_dir in sorted(category_dir.iterdir()):
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            skill = _parse_skill_md(skill_file, hard_fail=False)
            if skill is None:
                continue
            # Name validation for repo-owned (Tier 2)
            if not _NAME_RE.match(skill.name):
                if base_dir == _RESOURCES_DIR:
                    raise RuntimeError(
                        f"Invalid name '{skill.name}' in repo-owned {skill_file}"
                    )
                logger.warning(f"Skipping skill with invalid name '{skill.name}' in {skill_file}")
                continue
            if skill.name in results:
                logger.warning(
                    f"Duplicate skill '{skill.name}' in same tier: "
                    f"keeping {results[skill.name].source_path}, skipping {skill.source_path}"
                )
                continue
            results[skill.name] = skill

    return results


def _scan_legacy_yaml(custom_dir: Path) -> Dict[str, SkillDefinition]:
    """Scan Tier 3b: config/skills/*.yaml (non-recursive, legacy format)."""
    results: Dict[str, SkillDefinition] = {}

    if not custom_dir.exists():
        return results

    for path in sorted(custom_dir.glob("*.yaml")):
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            if not data or not isinstance(data, dict):
                continue

            name = data.get("name", path.stem)
            skill = SkillDefinition(
                name=name,
                description=data.get("description", ""),
                prompt_template=data.get("prompt_template", ""),
                required_params=data.get("required_params", []),
                aliases=data.get("aliases", []),
                source_path=str(path),
            )

            if not skill.prompt_template:
                logger.warning(f"Empty prompt_template in {path}, skipping")
                continue

            if name in results:
                logger.warning(f"Duplicate YAML skill '{name}', skipping {path}")
                continue

            results[name] = skill
            logger.debug(f"Loaded legacy YAML skill '{name}' from {path}")
        except Exception as e:
            logger.warning(f"Failed to load skill from {path}: {e}")

    return results


# ── Alias + trigger rebuild ──────────────────────────────────

def _rebuild_alias_map() -> None:
    """Build _ALIAS_MAP from final SKILL_REGISTRY. Builtin aliases are protected."""
    _ALIAS_MAP.clear()

    # Collect builtin aliases first (reserved)
    builtin_aliases: set = set()
    for name, skill in SKILL_REGISTRY.items():
        if skill.category == "builtin" or name in _BUILTIN_SKILL_NAMES:
            for alias in skill.aliases:
                if alias in builtin_aliases:
                    raise RuntimeError(
                        f"Duplicate builtin alias '{alias}' — repo bug"
                    )
                builtin_aliases.add(alias)
                _ALIAS_MAP[alias] = name

    # Then non-builtin aliases
    for name, skill in SKILL_REGISTRY.items():
        if skill.category == "builtin" or name in _BUILTIN_SKILL_NAMES:
            continue
        for alias in skill.aliases:
            if alias in _ALIAS_MAP:
                logger.warning(
                    f"Alias '{alias}' for skill '{name}' conflicts with "
                    f"'{_ALIAS_MAP[alias]}' — skipping"
                )
                continue
            _ALIAS_MAP[alias] = name


def _rebuild_trigger_index() -> None:
    """Build _TRIGGER_INDEX from final SKILL_REGISTRY.

    Sorted by (-phrase_length, insertion_order) for longest-match-first.
    """
    _TRIGGER_INDEX.clear()

    entries: List[Tuple[int, int, str, SkillDefinition]] = []
    for idx, skill in enumerate(SKILL_REGISTRY.values()):
        if not skill.trigger:
            continue
        phrases = [p.strip() for p in skill.trigger.split("|") if p.strip()]
        for phrase in phrases:
            entries.append((-len(phrase), idx, phrase.lower(), skill))

    entries.sort(key=lambda e: (e[0], e[1]))
    _TRIGGER_INDEX.extend((phrase, skill) for _, _, phrase, skill in entries)


# ── Registry rebuild (single entry point) ────────────────────

def rebuild_skill_registry() -> int:
    """Complete rebuild: tiered scan → final winners → aliases → triggers.

    Scan order (last-write-wins across tiers):
        3b (legacy YAML) → 2 (packaged) → 3a (custom) → 1 (builtin)

    Builtin (Tier 1) cannot be overridden — RuntimeError if collision.
    """
    SKILL_REGISTRY.clear()
    _ALIAS_MAP.clear()
    _TRIGGER_INDEX.clear()

    # Tier 3b: legacy YAML (lowest priority)
    tier3b = _scan_legacy_yaml(_CUSTOM_DIR)
    SKILL_REGISTRY.update(tier3b)

    # Tier 2: packaged SKILL.md (resources/skills/{category}, excluding builtin/)
    tier2 = _scan_dir(_RESOURCES_DIR, exclude=["builtin"])
    for name, skill in tier2.items():
        if name in SKILL_REGISTRY:
            # Tier 2 overrides Tier 3b — pop + re-insert for dict order
            SKILL_REGISTRY.pop(name)
        SKILL_REGISTRY[name] = skill

    # Tier 3a: custom SKILL.md (overrides Tier 2)
    tier3a = _scan_dir(_CUSTOM_DIR / "custom" if (_CUSTOM_DIR / "custom").exists()
                        else _CUSTOM_DIR / "custom")
    for name, skill in tier3a.items():
        if name in _BUILTIN_SKILL_NAMES:
            logger.warning(f"Cannot override builtin '{name}' from custom, skipping")
            continue
        if name in SKILL_REGISTRY:
            SKILL_REGISTRY.pop(name)
        SKILL_REGISTRY[name] = skill

    # Tier 1: builtin (highest priority, cannot be overridden)
    tier1 = _scan_builtin(_RESOURCES_DIR / "builtin")
    for name, skill in tier1.items():
        if name in SKILL_REGISTRY:
            # Builtin takes precedence — pop the lower-tier version
            SKILL_REGISTRY.pop(name)
        SKILL_REGISTRY[name] = skill

    # Rebuild derived state
    _rebuild_alias_map()
    _rebuild_trigger_index()

    count = len(SKILL_REGISTRY)
    if count:
        logger.info(f"Skill registry: {count} skill(s) loaded")
    return count


# Initialize at import time
rebuild_skill_registry()


# ── Backward-compat shim ─────────────────────────────────────
# load_custom_skills() is still called from some paths; redirect to rebuild.

def load_custom_skills() -> int:
    """Legacy entry point — triggers full rebuild."""
    return rebuild_skill_registry() - len(_BUILTIN_SKILL_NAMES)


# ── Public API ───────────────────────────────────────────────

def list_skills() -> List[Dict[str, str]]:
    """Return skill info for display, sorted by (category, name)."""
    def sort_key(s: SkillDefinition) -> Tuple[str, str]:
        return (s.category or "", s.name)

    return [
        {
            "name": s.name,
            "description": s.description,
            "required_params": ", ".join(s.required_params) or "(none)",
            "aliases": ", ".join(s.aliases),
            "category": s.category or "",
        }
        for s in sorted(SKILL_REGISTRY.values(), key=sort_key)
    ]


def expand_skill(name: str, params: Dict[str, str]) -> Optional[str]:
    """Expand a skill template with parameters.

    Uses explicit str.replace() — safe for rich Markdown with {}, JSON, etc.
    Returns the expanded prompt string, or None if skill not found
    or required params are missing.
    """
    # Resolve alias
    resolved = _ALIAS_MAP.get(name, name)
    skill = SKILL_REGISTRY.get(resolved)
    if skill is None:
        return None

    # Check required params
    for p in skill.required_params:
        if p not in params or not params[p].strip():
            return None

    # Explicit replacement (not format_map — safe for rich content)
    result = skill.prompt_template
    for p in skill.required_params:
        if p in params:
            result = result.replace(f"{{{p}}}", params[p])
    return result


def parse_skill_command(arg: str) -> Tuple[Optional[str], Dict[str, str]]:
    """Parse a /skill command argument string.

    Examples:
        "full_analysis NVDA"  → ("full_analysis", {"ticker": "NVDA"})
        "scan"                → ("portfolio_scan", {})
        "ep TSLA"             → ("earnings_prep", {"ticker": "TSLA"})
        ""                    → (None, {})

    Returns (skill_name, params_dict). skill_name is None if empty input.
    """
    parts = arg.strip().split()
    if not parts:
        return None, {}

    name_or_alias = parts[0].lower()

    # Resolve alias
    resolved = _ALIAS_MAP.get(name_or_alias, name_or_alias)
    skill = SKILL_REGISTRY.get(resolved)
    if skill is None:
        return name_or_alias, {}  # Return unresolved name for error reporting

    # Map positional args to required_params
    params: Dict[str, str] = {}
    remaining = parts[1:]
    for i, param_name in enumerate(skill.required_params):
        if i < len(remaining):
            params[param_name] = remaining[i].upper()  # Tickers are uppercase

    return resolved, params


# ── Auto-trigger matching ────────────────────────────────────

def match_skill_trigger(question: str) -> SkillMatchResult:
    """Match user question against skill trigger phrases.

    Three-stage matching (strict → loose):
    1. Exact phrase match (boundary-aware)
    2. Ordered words match (boundary-aware)

    Returns SkillMatchResult with reason: "none", "unique", or "multiple".
    """
    if not _TRIGGER_INDEX or not question.strip():
        return SkillMatchResult()

    q_lower = question.lower()

    # Collect all matches with their best match stage + phrase length
    # Key: skill name → (stage_priority, -phrase_len)
    matches: Dict[str, Tuple[int, int, SkillDefinition]] = {}

    for phrase, skill in _TRIGGER_INDEX:
        if skill.name in matches:
            continue  # Already matched this skill at a better or equal level

        # Stage 1: exact phrase match
        pattern = r"\b" + re.escape(phrase) + r"\b"
        if re.search(pattern, q_lower):
            matches[skill.name] = (1, -len(phrase), skill)
            continue

        # Stage 2: ordered words match
        words = phrase.split()
        if len(words) >= 2:
            ordered_pattern = r"\b" + r"\b.*?\b".join(
                re.escape(w) for w in words
            ) + r"\b"
            if re.search(ordered_pattern, q_lower):
                matches[skill.name] = (2, -len(phrase), skill)

    if not matches:
        return SkillMatchResult()

    if len(matches) == 1:
        name, (_, _, skill) = next(iter(matches.items()))
        return SkillMatchResult(skill=skill, candidates=[name], reason="unique")

    # Multiple matches — check if one is strictly best
    sorted_matches = sorted(matches.items(), key=lambda kv: (kv[1][0], kv[1][1]))
    best_key = (sorted_matches[0][1][0], sorted_matches[0][1][1])
    second_key = (sorted_matches[1][1][0], sorted_matches[1][1][1])

    if best_key < second_key:
        # Unique best match
        name, (_, _, skill) = sorted_matches[0]
        return SkillMatchResult(
            skill=skill,
            candidates=[kv[0] for kv in sorted_matches],
            reason="unique",
        )

    # Tied — return multiple
    return SkillMatchResult(
        candidates=[kv[0] for kv in sorted_matches],
        reason="multiple",
    )


def build_auto_apply_context(skill: SkillDefinition, question: str) -> str:
    """Build context for auto-apply skills (paramless + auto_apply=True).

    Prepends full skill body to the user's question.
    Only call this when skill.can_auto_apply() is True.
    """
    assert skill.can_auto_apply(), "Must check can_auto_apply() before calling"
    expanded = expand_skill(skill.name, {})
    return f"[Auto-matched skill: {skill.name}]\n{expanded}\n\n[User query]\n{question}"


def render_skill_suggestion_cli(result: SkillMatchResult) -> str:
    """Render CLI-only text hint for skill suggestion (Rich markup).

    Discord has its own embed logic in discord_bot.py.
    """
    if result.reason == "unique" and result.skill:
        params = " ".join(f"<{p.upper()}>" for p in result.skill.required_params)
        name = result.skill.name
        hint = f"[dim]Skill suggestion: {name} — use /skill {name}"
        if params:
            hint += f" {params}"
        hint += "[/dim]"
        return hint
    elif result.reason == "multiple":
        names = ", ".join(result.candidates)
        return f"[dim]Multiple skills match: {names}. Use /skill <name> to choose.[/dim]"
    return ""


# ── Validation (optional, for --check-skills) ────────────────

def validate_skills(*, include_custom: bool = False) -> List[str]:
    """Validate skill definitions against ToolRegistry.

    Only validates data_sources fields. Returns list of warning messages.
    Not called at import time — use for manual checks or tests.
    """
    warnings: List[str] = []

    try:
        from src.tools.registry import ToolRegistry
        registry = ToolRegistry()
        available_tools = set(registry.get_tool_names())
    except Exception:
        warnings.append("Cannot load ToolRegistry — skipping data_sources validation")
        return warnings

    for name, skill in SKILL_REGISTRY.items():
        if not include_custom and skill.source_path and "config/" in skill.source_path:
            continue
        if not skill.data_sources:
            continue
        for tool in skill.data_sources.get("required", []):
            if tool not in available_tools:
                warnings.append(
                    f"Skill '{name}': required data source '{tool}' not in ToolRegistry"
                )

    return warnings
"""Exercise the artifact guard with disposable repositories, never the project index."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "tests" / "repository_hygiene.py"
HOOK = ROOT / ".githooks" / "pre-commit"
WORKFLOW = ROOT / ".github" / "workflows" / "repository-hygiene.yml"
FORBIDDEN = (
    ".superpowers/run/receipt.txt",
    "docs/superpowers/evidence/run/receipt.txt",
    "data/verification/run/receipt.txt",
)


@pytest.fixture
def git_env(tmp_path):
    return {
        "PATH": os.pathsep.join((str(Path(sys.executable).parent), os.defpath)),
        "HOME": str(tmp_path),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_CEILING_DIRECTORIES": str(tmp_path.parent),
        "PYTHONDONTWRITEBYTECODE": "1",
        "LC_ALL": "C",
    }


def git(repo, env, *args, check=True):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="backslashreplace",
        timeout=15,
        check=check,
    )


@pytest.fixture
def repo(tmp_path, git_env):
    root = tmp_path / "repository with spaces"
    root.mkdir()
    git(root, git_env, "init", "--quiet", "--template=")
    git(root, git_env, "config", "user.name", "Artifact Guard Test")
    git(root, git_env, "config", "user.email", "guard@example.invalid")
    git(root, git_env, "config", "commit.gpgsign", "false")
    return root


def write(repo, name, content="fixture\n"):
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def seed(repo, env, *names):
    for name in names:
        write(repo, name)
    git(repo, env, "add", "--", *names)
    git(repo, env, "commit", "--quiet", "-m", "Seed fixture")


def guard(repo, env, *args, stdin=None):
    # -I -S proves the command needs neither application imports nor site packages.
    return subprocess.run(
        [sys.executable, "-I", "-S", str(CHECKER), *args],
        cwd=repo,
        env=env,
        capture_output=True,
        input=stdin,
        text=True,
        encoding="utf-8",
        errors="backslashreplace",
        timeout=15,
    )


def assert_blocked(result, name):
    assert result.returncode == 1, result.stderr
    assert "repository hygiene" in result.stderr.lower()
    assert ascii(name) in result.stderr
    assert result.stdout == ""


@pytest.mark.parametrize("initial", [True, False], ids=["unborn", "with-head"])
@pytest.mark.parametrize("args", [(), ("--all-tracked",)])
@pytest.mark.parametrize(
    "name",
    [
        ".superpowers",
        "docs/superpowers/evidence",
        "data/verification",
        *FORBIDDEN,
        ".superpowers/space tab\tnewline\nquote'\"backslash\\-\udcff.txt",
        "docs/superpowers/evidence/space tab\tnewline\nquote'\"backslash\\.txt",
    ],
)
def test_force_added_ignored_artifacts_are_blocked(repo, git_env, name, initial, args):
    if not initial:
        seed(repo, git_env, "src/baseline.py")
    write(repo, ".gitignore", "/.superpowers\n/docs/superpowers/evidence\n/data/verification\n")
    write(repo, name)
    git(repo, git_env, "check-ignore", "--", name)
    git(repo, git_env, "add", "--force", "--", name)

    assert_blocked(guard(repo, git_env, *args), name)


@pytest.mark.parametrize("name", [".superpowers", "docs/superpowers/evidence", "data/verification"])
@pytest.mark.parametrize("args", [(), ("--all-tracked",)])
def test_symlinks_at_forbidden_roots_are_blocked(repo, git_env, name, args):
    target = write(repo, "src/target.py")
    link = repo / name
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)
    git(repo, git_env, "add", "--", name)

    assert_blocked(guard(repo, git_env, *args), name)


@pytest.mark.parametrize("name", [".superpowers", "docs/superpowers/evidence", "data/verification"])
@pytest.mark.parametrize("to_symlink", [True, False], ids=["file-to-link", "link-to-file"])
def test_type_changes_at_forbidden_roots_are_blocked(repo, git_env, name, to_symlink):
    target = write(repo, "src/target.py")
    artifact = repo / name
    artifact.parent.mkdir(parents=True, exist_ok=True)
    if to_symlink:
        write(repo, name)
    else:
        artifact.symlink_to(target)
    git(repo, git_env, "add", "--", name)
    git(repo, git_env, "commit", "--quiet", "-m", "Seed legacy artifact")
    artifact.unlink()
    if to_symlink:
        artifact.symlink_to(target)
    else:
        write(repo, name)
    git(repo, git_env, "add", "--", name)
    assert git(repo, git_env, "diff", "--cached", "--name-status", "-z").stdout == "T\0" + name + "\0"

    assert_blocked(guard(repo, git_env), name)


@pytest.mark.parametrize("args", [(), ("--all-tracked",)])
@pytest.mark.parametrize("initial", [True, False], ids=["unborn", "with-head"])
def test_empty_index_and_clean_tree_pass(repo, git_env, initial, args):
    if not initial:
        seed(repo, git_env, "src/baseline.py")

    result = guard(repo, git_env, *args)

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""


@pytest.mark.parametrize("args", [(), ("--all-tracked",)])
def test_nearby_paths_and_untracked_artifacts_are_allowed(repo, git_env, args):
    allowed = (
        ".superpowers-notes/receipt.txt",
        "docs/superpowers/evidence-notes/receipt.txt",
        "data/verification-notes/receipt.txt",
        "docs/superpowers/specs/design.md",
        "docs/superpowers/plans/plan.md",
        "src/.superpowers/receipt.txt",
        "other/docs/superpowers/evidence/receipt.txt",
        "src/line\n.superpowers\nfile.py",
        "src/-space tab\tquote'\"backslash\\.py",
    )
    for name in (*allowed, *FORBIDDEN):
        write(repo, name)
    git(repo, git_env, "add", "--", *allowed)

    result = guard(repo, git_env, *args)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("name", FORBIDDEN)
def test_modifications_of_tracked_artifacts_are_blocked(repo, git_env, name):
    seed(repo, git_env, name)
    write(repo, name, "changed\n")
    git(repo, git_env, "add", "--", name)

    assert_blocked(guard(repo, git_env), name)


@pytest.mark.parametrize("name", FORBIDDEN)
@pytest.mark.parametrize("args", [(), ("--all-tracked",)])
def test_staged_deletions_pass_even_if_local_artifacts_remain(repo, git_env, name, args):
    seed(repo, git_env, name)
    git(repo, git_env, "rm", "--cached", "--", name)

    result = guard(repo, git_env, *args)

    assert result.returncode == 0, result.stderr
    assert (repo / name).is_file()


def test_worktree_removal_does_not_hide_a_staged_artifact(repo, git_env):
    name = FORBIDDEN[0]
    write(repo, name)
    git(repo, git_env, "add", "--", name)
    (repo / name).unlink()

    assert_blocked(guard(repo, git_env), name)


@pytest.mark.parametrize("name", FORBIDDEN)
def test_legacy_artifacts_only_block_full_tree_mode(repo, git_env, name):
    seed(repo, git_env, name, "src/baseline.py")
    write(repo, "src/baseline.py", "changed\n")
    git(repo, git_env, "add", "--", "src/baseline.py")
    nested = repo / "src"
    git(repo, git_env, "config", "diff.relative", "true")

    result = guard(nested, git_env)

    assert result.returncode == 0, result.stderr
    assert_blocked(guard(nested, git_env, "--all-tracked"), name)


@pytest.mark.parametrize("name", FORBIDDEN)
@pytest.mark.parametrize("copy", [False, True], ids=["rename", "copy"])
@pytest.mark.parametrize("into_forbidden", [False, True], ids=["out", "into"])
def test_rename_and_copy_destinations_are_checked(repo, git_env, name, copy, into_forbidden):
    allowed = "src/space tab\tnewline\nquote'\"backslash\\.py"
    source, destination = (allowed, name) if into_forbidden else (name, allowed)
    seed(repo, git_env, source)
    (repo / destination).parent.mkdir(parents=True, exist_ok=True)
    if copy:
        shutil.copyfile(repo / source, repo / destination)
    else:
        (repo / source).rename(repo / destination)
    git(repo, git_env, "add", "--all")
    status = git(
        repo, git_env, "diff", "--cached", "--name-status", "-z",
        "--find-renames", "--find-copies-harder",
    ).stdout
    assert status.split("\0", 1)[0] == ("C100" if copy else "R100")
    git(repo, git_env, "config", "diff.renames", "copies")
    git(repo, git_env, "config", "diff.relative", "true")

    result = guard(repo / "src", git_env)

    if into_forbidden:
        assert_blocked(result, name)
    else:
        assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("args", [(), ("--all-tracked",)])
def test_git_failure_outside_a_repository_is_not_a_pass(tmp_path, git_env, args):
    result = guard(tmp_path, git_env, *args)

    assert result.returncode == 2, result.stderr
    assert "git" in result.stderr.lower()
    assert "not a git repository" in result.stderr.lower()
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("args", [(), ("--all-tracked",)])
def test_corrupt_index_is_reported_as_a_git_failure(repo, git_env, args):
    seed(repo, git_env, "src/baseline.py")
    (repo / ".git" / "index").write_bytes(b"corrupt index\n")

    result = guard(repo, git_env, *args)

    assert result.returncode == 2, result.stderr
    assert "git" in result.stderr.lower()
    assert "index" in result.stderr.lower()
    assert "fatal:" in result.stderr.lower()
    assert "Traceback" not in result.stderr


def test_missing_git_is_reported_as_a_failure(repo, git_env, tmp_path):
    result = guard(repo, dict(git_env, PATH=str(tmp_path / "no-executables")))

    assert result.returncode == 2, result.stderr
    assert "git" in result.stderr.lower()
    assert "No such file" in result.stderr
    assert "Traceback" not in result.stderr


def test_broken_head_is_not_treated_as_an_initial_commit(repo, git_env):
    seed(repo, git_env, "src/baseline.py")
    ref = git(repo, git_env, "symbolic-ref", "HEAD").stdout.strip()
    (repo / ".git" / ref).write_text("1" * 40 + "\n", encoding="ascii")

    result = guard(repo, git_env)

    assert result.returncode == 2, result.stderr
    assert "git" in result.stderr.lower()
    assert "fatal:" in result.stderr.lower()
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("name", FORBIDDEN)
def test_full_tree_check_catches_artifacts_in_a_fresh_clone(repo, git_env, tmp_path, name):
    seed(repo, git_env, name)
    clone = tmp_path / "fresh clone"
    git(tmp_path, git_env, "clone", "--quiet", "--no-hardlinks", str(repo), str(clone))
    assert git(clone, git_env, "diff", "--cached", "--name-only").stdout == ""

    assert_blocked(guard(clone, git_env, "--all-tracked"), name)


def install_hook(repo, env):
    assert HOOK.is_file(), "pre-commit hook is missing"
    assert os.access(HOOK, os.X_OK), "pre-commit hook must be executable"
    (repo / ".githooks").mkdir()
    (repo / "tests").mkdir()
    shutil.copy2(HOOK, repo / ".githooks" / "pre-commit")
    shutil.copy2(CHECKER, repo / "tests" / "repository_hygiene.py")
    git(repo, env, "config", "core.hooksPath", ".githooks")


@pytest.mark.parametrize("initial", [True, False], ids=["unborn", "with-head"])
@pytest.mark.parametrize("name", FORBIDDEN)
def test_hook_blocks_actual_commit_of_force_added_artifacts(repo, git_env, name, initial):
    if not initial:
        seed(repo, git_env, "src/baseline.py")
    install_hook(repo, git_env)
    write(repo, ".gitignore", "/.superpowers\n/docs/superpowers/evidence\n/data/verification\n")
    write(repo, name)
    git(repo, git_env, "check-ignore", "--", name)
    git(repo, git_env, "add", "--force", "--", name)
    before = git(repo, git_env, "rev-parse", "--verify", "HEAD", check=False)

    result = git(repo, git_env, "commit", "-m", "Must be blocked", check=False)

    assert_blocked(result, name)
    after = git(repo, git_env, "rev-parse", "--verify", "HEAD", check=False)
    assert (after.returncode, after.stdout) == (before.returncode, before.stdout)
    assert git(repo, git_env, "diff", "--cached", "--name-only", "-z").stdout == name + "\0"


@pytest.mark.parametrize("name", FORBIDDEN)
@pytest.mark.parametrize("change", ["modify", "delete", "unrelated"])
def test_hook_blocks_modifications_but_allows_cleanup_and_code(repo, git_env, name, change):
    seed(repo, git_env, name, "src/baseline.py")
    install_hook(repo, git_env)
    if change == "delete":
        git(repo, git_env, "rm", "--cached", "--", name)
    else:
        changed = name if change == "modify" else "src/baseline.py"
        write(repo, changed, "changed\n")
        git(repo, git_env, "add", "--", changed)
    before = git(repo, git_env, "rev-parse", "HEAD").stdout

    result = git(repo, git_env, "commit", "-m", "Test staged change", check=False)

    after = git(repo, git_env, "rev-parse", "HEAD").stdout
    if change == "modify":
        assert_blocked(result, name)
        assert after == before
    else:
        assert result.returncode == 0, result.stderr
        assert after != before
        if change == "delete":
            assert name not in git(repo, git_env, "ls-files", "-z").stdout.split("\0")
            assert (repo / name).is_file()


def test_hook_resolves_checker_from_a_nested_working_directory(repo, git_env):
    install_hook(repo, git_env)
    nested = repo / "src"
    nested.mkdir()
    name = FORBIDDEN[0]
    write(repo, name)
    git(repo, git_env, "add", "--", name)
    git(repo, git_env, "config", "diff.relative", "true")

    result = subprocess.run(
        [str(repo / ".githooks" / "pre-commit")],
        cwd=nested, env=git_env, capture_output=True, text=True, timeout=15,
    )

    assert_blocked(result, name)


def test_hook_works_in_a_linked_worktree(repo, git_env, tmp_path):
    install_hook(repo, git_env)
    git(repo, git_env, "add", "--", ".githooks/pre-commit", "tests/repository_hygiene.py")
    git(repo, git_env, "commit", "--quiet", "-m", "Install fixture guard")
    linked = tmp_path / "linked worktree with spaces"
    git(repo, git_env, "worktree", "add", "--quiet", "--detach", str(linked))
    assert (linked / ".git").is_file()
    name = FORBIDDEN[0]
    write(linked, name)
    git(linked, git_env, "add", "--", name)

    result = git(linked, git_env, "commit", "-m", "Must be blocked", check=False)

    assert_blocked(result, name)


def test_ci_runs_full_guard_on_push_and_pull_request(repo, git_env):
    assert WORKFLOW.is_file(), "repository hygiene workflow is missing"
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert set(workflow["on"]) == {"push", "pull_request"}
    job, = workflow["jobs"].values()
    commands = [step["run"] for step in job["steps"] if "run" in step]
    assert commands, "CI must execute the guard, not just check out the repository"
    (repo / "tests").mkdir()
    shutil.copy2(CHECKER, repo / "tests" / "repository_hygiene.py")
    seed(repo, git_env, "src/baseline.py")

    def run_checks():
        return subprocess.run(
            ["/bin/sh", "-ec", "\n".join(commands)],
            cwd=repo, env=git_env, capture_output=True, text=True, timeout=15,
        )

    clean = run_checks()
    assert clean.returncode == 0, clean.stderr
    seed(repo, git_env, *FORBIDDEN)
    assert git(repo, git_env, "diff", "--cached", "--name-only").stdout == ""

    result = run_checks()

    for name in FORBIDDEN:
        assert_blocked(result, name)


def remove_artifacts(repo, env, *names):
    git(repo, env, "rm", "--", *names)
    git(repo, env, "commit", "--quiet", "-m", "Remove legacy artifacts")


@pytest.mark.parametrize("name", (*FORBIDDEN, ".superpowers", "docs/superpowers/evidence", "data/verification"))
def test_history_rejects_artifacts_even_after_deletion(repo, git_env, name):
    seed(repo, git_env, name)
    remove_artifacts(repo, git_env, name)
    assert guard(repo, git_env, "--all-tracked").returncode == 0

    result = guard(repo, git_env, "--history-ref", "HEAD")

    assert result.returncode == 1, result.stderr
    assert "history" in result.stderr.lower()


@pytest.mark.parametrize("name", [".superpowers", "docs/superpowers/evidence", "data/verification"])
def test_history_checks_root_symlinks(repo, git_env, name):
    target = write(repo, "src/target.py")
    link = repo / name
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)
    git(repo, git_env, "add", "--", name)
    git(repo, git_env, "commit", "--quiet", "-m", "Link fixture")
    remove_artifacts(repo, git_env, name)
    assert guard(repo, git_env, "--history-ref", "HEAD").returncode == 1


def test_history_checks_second_parent_even_when_merge_keeps_clean_tree(repo, git_env):
    seed(repo, git_env, "src/allowed.py")
    main = git(repo, git_env, "branch", "--show-current").stdout.strip()
    git(repo, git_env, "checkout", "--quiet", "-b", "old-artifacts")
    seed(repo, git_env, FORBIDDEN[0])
    remove_artifacts(repo, git_env, FORBIDDEN[0])
    git(repo, git_env, "checkout", "--quiet", main)
    seed(repo, git_env, "src/another.py")
    git(repo, git_env, "merge", "--quiet", "--no-ff", "-s", "ours", "old-artifacts", "-m", "Merge old history")
    assert guard(repo, git_env, "--all-tracked").returncode == 0
    assert guard(repo, git_env, "--history-ref", "HEAD").returncode == 1


def test_history_does_not_deduplicate_blob_path_names(repo, git_env):
    seed(repo, git_env, "src/allowed.py")
    seed(repo, git_env, FORBIDDEN[1])
    assert git(repo, git_env, "rev-parse", "HEAD:src/allowed.py").stdout == git(
        repo, git_env, "rev-parse", "HEAD:" + FORBIDDEN[1],
    ).stdout
    remove_artifacts(repo, git_env, FORBIDDEN[1])
    assert guard(repo, git_env, "--history-ref", "HEAD").returncode == 1


def test_history_allows_similar_prefixes_and_ignores_unoffered_refs(repo, git_env):
    seed(repo, git_env, ".superpowers-notes/a", "docs/superpowers/evidence-notes/a",
         "data/verification-notes/a", "src/.superpowers/a", "docs/superpowers/plans/a")
    clean = git(repo, git_env, "rev-parse", "HEAD").stdout.strip()
    seed(repo, git_env, FORBIDDEN[0])
    result = guard(repo / "src", git_env, "--history-ref", clean)
    assert result.returncode == 0, result.stderr


def test_history_checks_all_explicit_refs(repo, git_env):
    seed(repo, git_env, "src/a.py")
    clean = git(repo, git_env, "rev-parse", "HEAD").stdout.strip()
    seed(repo, git_env, FORBIDDEN[0])
    remove_artifacts(repo, git_env, FORBIDDEN[0])
    assert guard(repo, git_env, "--history-ref", clean, "--history-ref", "HEAD").returncode == 1


def test_history_refuses_shallow_history(repo, git_env, tmp_path):
    seed(repo, git_env, FORBIDDEN[0])
    remove_artifacts(repo, git_env, FORBIDDEN[0])
    clone = tmp_path / "shallow"
    git(tmp_path, git_env, "clone", "--quiet", "--depth=1", repo.as_uri(), str(clone))
    assert guard(clone, git_env, "--all-tracked").returncode == 0
    result = guard(clone, git_env, "--history-ref", "HEAD")
    assert result.returncode == 2, result.stderr
    assert "shallow" in result.stderr.lower()


@pytest.mark.parametrize("revision", ["missing-ref", "--all", "HEAD:src/a.py"])
def test_history_refuses_unresolvable_or_noncommit_refs(repo, git_env, revision):
    seed(repo, git_env, "src/a.py")
    result = guard(repo, git_env, "--history-ref=" + revision)
    assert result.returncode == 2, result.stderr
    assert "git command failed" in result.stderr.lower()


def test_history_does_not_allow_replace_refs_to_hide_artifacts(repo, git_env):
    seed(repo, git_env, "src/a.py")
    clean = git(repo, git_env, "rev-parse", "HEAD").stdout.strip()
    seed(repo, git_env, FORBIDDEN[0])
    remove_artifacts(repo, git_env, FORBIDDEN[0])
    git(repo, git_env, "replace", "HEAD", clean)
    assert guard(repo, git_env, "--history-ref", "HEAD").returncode == 1


@pytest.mark.parametrize("cached", [False, True], ids=["uncached", "commit-graph"])
@pytest.mark.parametrize("pre_push", [False, True], ids=["history", "pre-push"])
def test_history_missing_ancestor_is_not_a_pass(repo, git_env, cached, pre_push):
    seed(repo, git_env, "src/a.py")
    parent = git(repo, git_env, "rev-parse", "HEAD").stdout.strip()
    seed(repo, git_env, "src/b.py")
    tip = git(repo, git_env, "rev-parse", "HEAD").stdout.strip()
    if cached:
        git(repo, git_env, "commit-graph", "write", "--reachable")
    (repo / ".git" / "objects" / parent[:2] / parent[2:]).unlink()
    result = guard(repo, git_env, "--pre-push", stdin=push_line(tip)) if pre_push else guard(
        repo, git_env, "--history-ref", "HEAD",
    )
    assert result.returncode == 2, result.stderr
    assert "git command failed" in result.stderr.lower()


@pytest.mark.parametrize("settings,name,expected", [
    ({"GIT_LITERAL_PATHSPECS": "1"}, FORBIDDEN[0], 1),
    ({"GIT_GLOB_PATHSPECS": "1"}, FORBIDDEN[1], 1),
    ({"GIT_NOGLOB_PATHSPECS": "1"}, FORBIDDEN[2], 1),
    ({"GIT_LITERAL_PATHSPECS": "1", "GIT_GLOB_PATHSPECS": "1"}, FORBIDDEN[0], 1),
    ({"GIT_ICASE_PATHSPECS": "1"}, ".SUPERPOWERS/allowed", 0),
])
@pytest.mark.parametrize("pre_push", [False, True], ids=["history", "pre-push"])
def test_history_normalizes_inherited_pathspec_modes(repo, git_env, settings, name, expected, pre_push):
    seed(repo, git_env, name)
    remove_artifacts(repo, git_env, name)
    tip = git(repo, git_env, "rev-parse", "HEAD").stdout.strip()
    inherited = dict(git_env, **settings)
    result = guard(repo, inherited, "--pre-push", stdin=push_line(tip)) if pre_push else guard(
        repo, inherited, "--history-ref", "HEAD",
    )
    assert result.returncode == expected, result.stderr


def push_line(local_oid, remote_oid=None, ref="refs/heads/master"):
    return f"{ref} {local_oid} {ref} {remote_oid or '0' * 40}\n"


def test_pre_push_allows_empty_and_deletion_only_pushes_without_head(repo, git_env):
    assert guard(repo, git_env, "--pre-push", stdin="").returncode == 0
    result = guard(repo, git_env, "--pre-push", stdin=push_line("0" * 40, "1" * 40))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("tag", [False, True])
def test_pre_push_checks_every_offered_ref_including_annotated_tags(repo, git_env, tag):
    seed(repo, git_env, "src/a.py")
    clean = git(repo, git_env, "rev-parse", "HEAD").stdout.strip()
    seed(repo, git_env, FORBIDDEN[2])
    remove_artifacts(repo, git_env, FORBIDDEN[2])
    ref = "refs/heads/legacy"
    if tag:
        git(repo, git_env, "tag", "-a", "legacy", "-m", "Old history")
        ref = "refs/tags/legacy"
    tip = git(repo, git_env, "rev-parse", ref if tag else "HEAD").stdout.strip()
    result = guard(repo, git_env, "--pre-push", stdin=push_line(clean) + push_line(tip, ref=ref))
    assert result.returncode == 1, result.stderr


def test_pre_push_allows_clean_commit_tags(repo, git_env):
    seed(repo, git_env, "src/a.py")
    git(repo, git_env, "tag", "-a", "clean", "-m", "Clean history")
    tip = git(repo, git_env, "rev-parse", "refs/tags/clean").stdout.strip()
    result = guard(repo, git_env, "--pre-push", stdin=push_line(tip, ref="refs/tags/clean"))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("data", ["invalid\n", "HEAD not-an-oid refs/heads/a " + "0" * 40,
    "HEAD " + "1" * 40 + " refs/heads/a invalid\n"])
def test_pre_push_rejects_malformed_input(repo, git_env, data):
    result = guard(repo, git_env, "--pre-push", stdin=data)
    assert result.returncode == 2, result.stderr
    assert "pre-push" in result.stderr.lower()


def test_pre_push_noncommit_tip_is_not_a_pass(repo, git_env):
    seed(repo, git_env, "src/a.py")
    blob = git(repo, git_env, "rev-parse", "HEAD:src/a.py").stdout.strip()
    result = guard(repo, git_env, "--pre-push", stdin=push_line(blob, ref="refs/tags/blob"))
    assert result.returncode == 2, result.stderr


@pytest.mark.parametrize("literal", [False, True], ids=["default-pathspecs", "inherited-literal"])
def test_pre_push_hook_blocks_dirty_ancestry_before_remote_changes(repo, git_env, tmp_path, literal):
    seed(repo, git_env, "src/a.py")
    remote = tmp_path / "remote.git"
    git(tmp_path, git_env, "init", "--quiet", "--bare", "--template=", str(remote))
    git(repo, git_env, "remote", "add", "fixture", str(remote))
    hook = write(repo, ".githooks/pre-push", '#!/bin/sh\nset -eu\nrepo_root=$(git rev-parse --show-toplevel)\nexec python3 -I -S "$repo_root/tests/repository_hygiene.py" --pre-push\n')
    hook.chmod(0o755)
    (repo / "tests").mkdir()
    shutil.copy2(CHECKER, repo / "tests/repository_hygiene.py")
    git(repo, git_env, "config", "core.hooksPath", ".githooks")
    clean = git(repo, git_env, "push", "fixture", "HEAD:refs/heads/main", check=False)
    assert clean.returncode == 0, clean.stderr
    before = git(remote, git_env, "rev-parse", "refs/heads/main").stdout
    seed(repo, git_env, FORBIDDEN[0])
    remove_artifacts(repo, git_env, FORBIDDEN[0])

    inherited = dict(git_env, GIT_LITERAL_PATHSPECS="1") if literal else git_env
    result = git(repo, inherited, "push", "fixture", "HEAD:refs/heads/main", check=False)

    assert result.returncode != 0
    assert "forbidden" in result.stderr.lower()
    assert git(remote, git_env, "rev-parse", "refs/heads/main").stdout == before


@pytest.mark.parametrize("args", [("--all-tracked", "--history-ref", "HEAD"),
    ("--pre-push", "--history-ref", "HEAD"), ("--pre-push", "--all-tracked")])
def test_history_modes_are_mutually_exclusive(repo, git_env, args):
    assert guard(repo, git_env, *args, stdin="").returncode == 2

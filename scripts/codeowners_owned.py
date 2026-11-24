#!/usr/bin/env python3
"""Say whether a CODEOWNERS file owns a path: the proof behind .github/CODEOWNERS.

GitHub applies the LAST pattern that matches a path, and a matching line that
names no owner releases the path. This reads a CODEOWNERS file with those rules
and answers owned or released for a path. It is a record-keeping tool, not a
gate: it reads a file and prints, and writes nothing.

    codeowners_owned.py --codeowners FILE --check
        Compare the file against SAMPLES below. Exit 0 when every sample is
        owned or released as expected, 1 with one line per mismatch otherwise.
    codeowners_owned.py --codeowners FILE --count --tree FILE
        Print "owned N of M" for the paths listed one per line in the tree file
        (for example the output of `git ls-files`).

Stdlib only. See codeowners_owned.md."""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
from typing import NamedTuple


class Rule(NamedTuple):
    pattern: str
    regex: re.Pattern[str]
    owners: tuple[str, ...]


# One path per kept class and one per released class. The second field is
# whether the path must be owned. Edit this table with .github/CODEOWNERS.
SAMPLES: tuple[tuple[str, bool, str], ...] = (
    # Rules and the owner's words.
    ("CLAUDE.md", True, "rules"),
    ("docs/CLAUDE.md", True, "rules, any depth"),
    ("AUTHORISATIONS.md", True, "rules"),
    (".claude/settings.json", True, "rules"),
    # Gate scripts and their tests and fixtures: the required checks run them.
    ("scripts/assert-no-committed-pulumi-secrets.py", True, "gate script"),
    ("scripts/assert-environment-gated.py", True, "gate script"),
    ("scripts/test_assert_no_inline_credential.py", True, "gate test"),
    ("scripts/test_secret_checks.py", True, "gate test"),
    ("scripts/test_plan_job.py", True, "gate test"),
    ("scripts/test_verify_attestations_job.py", True, "gate test"),
    ("scripts/codeowners_owned.py", True, "proof tool of this file"),
    ("scripts/test_codeowners_owned.py", True, "gate test"),
    ("scripts/testdata/codeowners/before.txt", True, "gate fixture"),
    ("test/render.test.ts", True, "test that the stack records no secret"),
    (".pre-commit-config.yaml", True, "runs on contributor machines"),
    # Workflows and the standards escape hatches.
    (".github/workflows/infra-ci.yml", True, "workflow"),
    (".github/dependabot.yml", True, "dependency update policy"),
    (".github/CODEOWNERS", True, "this file"),
    (".github/notes.md", True, "nothing under .github is released"),
    (".standardsignore", True, "escape hatch"),
    (".standards.mode", True, "escape hatch"),
    (".docs-lint.mode", True, "escape hatch"),
    (".standards-db-tooling", True, "escape hatch"),
    # Human-facing docs and the owner's words.
    ("README.md", True, "human-facing doc"),
    ("LICENSE", True, "legal text"),
    # Released: documents, app and infra code, the other scripts, install files,
    # editor and ignore files, the version pin, the lockfile, the image pin.
    ("RUNBOOK-bootstrap.md", False, "document"),
    ("docs/new-page.md", False, "new document"),
    ("scripts/image-changed.md", False, "script document"),
    ("scripts/codeowners_owned.md", False, "script document"),
    ("scripts/image-changed.py", False, "script that gates nothing"),
    ("scripts/summarise-plan.py", False, "script that gates nothing"),
    ("scripts/test_image_changed.py", False, "test of a script that gates nothing"),
    ("scripts/testdata/image-changed/plan-all-same.json", False, "fixture"),
    ("scripts/new-check.py", False, "new script, agent-reviewed"),
    ("theme/build_theme.py", False, "theme code"),
    ("Pulumi.yaml", False, "Pulumi project file"),
    ("Pulumi.blog.yaml", False, "stack config"),
    ("index.ts", False, "Pulumi program"),
    ("config.ts", False, "Pulumi program"),
    ("tsconfig.json", False, "loader config"),
    ("package.json", False, "install-time inputs"),
    ("pnpm-workspace.yaml", False, "install-script allowlist"),
    (".npmrc", False, "registry config"),
    (".pnpmfile.cjs", False, "install hook"),
    ("known_hosts", False, "what the deploy ssh trusts"),
    (".nvmrc", False, "version pin"),
    ("pnpm-lock.yaml", False, "lockfile"),
    ("image-pin.txt", False, "image pin, no ciphertext"),
    (".editorconfig", False, "editor file"),
    (".gitignore", False, "ignore file"),
    (".prettierignore", False, "ignore file"),
)


def compile_pattern(pattern: str) -> re.Pattern[str]:
    """Translate one CODEOWNERS pattern (gitignore style) to a regex on a path."""
    if pattern.startswith(("!", "[")) or "\\" in pattern:
        raise ValueError(f"unsupported CODEOWNERS pattern: {pattern!r}")
    directory = pattern.endswith("/")
    body = pattern.rstrip("/")
    anchored = body.startswith("/") or "/" in body
    body = body.lstrip("/")
    out: list[str] = []
    i = 0
    while i < len(body):
        if body.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif body.startswith("/**", i) and i + 3 == len(body):
            out.append("/.*")
            i += 3
        elif body.startswith("**", i):
            out.append(".*")
            i += 2
        elif body[i] == "*":
            out.append("[^/]*")
            i += 1
        elif body[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(body[i]))
            i += 1
    prefix = "^" if anchored else "^(?:.*/)?"
    suffix = "/.+" if directory else "(?:/.*)?"
    return re.compile(prefix + "".join(out) + suffix + "$")


def parse(text: str) -> list[Rule]:
    rules: list[Rule] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        owners: list[str] = []
        for field in fields[1:]:
            if field.startswith("#"):
                break  # A trailing comment ends the owner list.
            owners.append(field)
        rules.append(Rule(fields[0], compile_pattern(fields[0]), tuple(owners)))
    return rules


def owners_of(rules: list[Rule], path: str) -> tuple[str, ...]:
    """The owners of a path: the last matching rule wins, none if no rule matches."""
    result: tuple[str, ...] = ()
    for rule in rules:
        if rule.regex.match(path):
            result = rule.owners
    return result


def is_owned(rules: list[Rule], path: str) -> bool:
    return bool(owners_of(rules, path))


def mismatches(rules: list[Rule]) -> list[str]:
    """One line per sample whose owned or released answer is not the expected one."""
    found: list[str] = []
    for path, expected, why in SAMPLES:
        actual = is_owned(rules, path)
        if actual != expected:
            want = "owned" if expected else "released"
            got = "owned" if actual else "released"
            found.append(f"MISMATCH {path} ({why}): expected {want}, got {got}")
    return found


def has_catch_all(rules: list[Rule]) -> bool:
    return any(rule.pattern in ("*", "/*", "**", "/**") for rule in rules)


def count(rules: list[Rule], paths: list[str]) -> tuple[int, int]:
    return sum(1 for p in paths if is_owned(rules, p)), len(paths)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Say whether a CODEOWNERS file owns a path.")
    ap.add_argument("--codeowners", required=True, type=pathlib.Path)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--count", action="store_true")
    ap.add_argument("--tree", type=pathlib.Path, help="paths, one per line (for --count)")
    args = ap.parse_args(argv)

    rules = parse(args.codeowners.read_text(encoding="utf-8"))
    if args.check:
        bad = mismatches(rules)
        for line in bad:
            print(line)
        if has_catch_all(rules):
            bad.append("catch-all")
            print("MISMATCH a bare catch-all line is present")
        total = len(SAMPLES)
        if bad:
            print(f"RED: {len(bad)} problem(s) against {total} sample paths")
            return 1
        print(f"GREEN: all {total} sample paths are owned or released as expected")
        return 0
    if args.tree is None:
        ap.error("--count needs --tree")
    paths = [p for p in args.tree.read_text(encoding="utf-8").splitlines() if p]
    owned, total = count(rules, paths)
    print(f"owned {owned} of {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

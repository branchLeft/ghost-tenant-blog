#!/usr/bin/env python3
"""Tests for codeowners_owned.py and for .github/CODEOWNERS itself.

Stdlib unittest; reads files and runs nothing else, so it is safe in a job that
holds no secret. See codeowners_owned.md."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import codeowners_owned as co  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
LIVE = (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
BEFORE = (ROOT / "scripts" / "testdata" / "codeowners" / "before.txt").read_text(encoding="utf-8")
TEAM = "@branchLeft/branchleft-admin"


def released_paths() -> set[str]:
    return {path for path, expected, _ in co.SAMPLES if not expected}


class LiveFile(unittest.TestCase):
    def test_every_sample_is_owned_or_released_as_expected(self) -> None:
        self.assertEqual([], co.mismatches(co.parse(LIVE)))

    def test_no_bare_catch_all(self) -> None:
        self.assertFalse(co.has_catch_all(co.parse(LIVE)))

    def test_every_rule_names_the_one_owner_team(self) -> None:
        for rule in co.parse(LIVE):
            self.assertEqual((TEAM,), rule.owners, rule.pattern)

    def test_the_owner_of_a_gate_script_loses_nothing_to_a_later_release(self) -> None:
        rules = co.parse(LIVE)
        for path, expected, _ in co.SAMPLES:
            if expected:
                self.assertTrue(co.is_owned(rules, path), path)

    def test_the_shared_lines_are_last(self) -> None:
        patterns = [rule.pattern for rule in co.parse(LIVE)]
        self.assertEqual(
            ["/.standardsignore", "/.standards.mode", "/.docs-lint*", "/.standards-db-tooling", "/.github/"],
            patterns[-5:],
        )


class OldFile(unittest.TestCase):
    def test_the_old_file_is_red_exactly_on_the_released_classes(self) -> None:
        rules = co.parse(BEFORE)
        wrong = {line.split()[1] for line in co.mismatches(rules)}
        self.assertEqual(released_paths(), wrong)

    def test_the_old_file_had_a_catch_all(self) -> None:
        self.assertTrue(co.has_catch_all(co.parse(BEFORE)))


class Sabotage(unittest.TestCase):
    def test_removing_the_python_line_leaves_scripts_unowned(self) -> None:
        kept = "\n".join(line for line in LIVE.splitlines() if not line.startswith("*.py"))
        wrong = co.mismatches(co.parse(kept))
        self.assertTrue(any("scripts/image-changed.py" in line for line in wrong))
        self.assertTrue(any("scripts/test_image_changed.py" in line for line in wrong))

    def test_removing_the_package_json_line_leaves_it_unowned(self) -> None:
        kept = "\n".join(line for line in LIVE.splitlines() if not line.startswith("package.json"))
        wrong = co.mismatches(co.parse(kept))
        self.assertTrue(any(" package.json " in line for line in wrong))

    def test_owning_the_image_pin_is_caught(self) -> None:
        wrong = co.mismatches(co.parse(LIVE.replace("known_hosts ", "image-pin.txt   @branchLeft/branchleft-admin\nknown_hosts ", 1)))
        self.assertTrue(any("image-pin.txt" in line for line in wrong))

    def test_a_release_line_after_the_shared_set_is_caught(self) -> None:
        wrong = co.mismatches(co.parse(LIVE + "\n/.github/notes.md\n"))
        self.assertTrue(any(".github/notes.md" in line for line in wrong))


class Matcher(unittest.TestCase):
    def owned(self, text: str, path: str) -> bool:
        return co.is_owned(co.parse(text), path)

    def test_a_pattern_with_no_slash_matches_at_any_depth(self) -> None:
        self.assertTrue(self.owned(f"*.py {TEAM}", "a/b/c.py"))
        self.assertTrue(self.owned(f"*.py {TEAM}", "c.py"))
        self.assertFalse(self.owned(f"*.py {TEAM}", "c.pyc"))

    def test_a_leading_slash_anchors_to_the_root(self) -> None:
        self.assertTrue(self.owned(f"/x.txt {TEAM}", "x.txt"))
        self.assertFalse(self.owned(f"/x.txt {TEAM}", "d/x.txt"))

    def test_a_middle_slash_anchors_to_the_root(self) -> None:
        self.assertTrue(self.owned(f"scripts/x.txt {TEAM}", "scripts/x.txt"))
        self.assertFalse(self.owned(f"scripts/x.txt {TEAM}", "a/scripts/x.txt"))

    def test_a_trailing_slash_is_a_directory_and_everything_under_it(self) -> None:
        self.assertTrue(self.owned(f"/d/ {TEAM}", "d/x/y.md"))
        self.assertFalse(self.owned(f"/d/ {TEAM}", "d"))
        self.assertFalse(self.owned(f"/d/ {TEAM}", "dd/x"))

    def test_double_star_crosses_directories_and_single_star_does_not(self) -> None:
        self.assertTrue(self.owned(f"/a/**/z.txt {TEAM}", "a/z.txt"))
        self.assertTrue(self.owned(f"/a/**/z.txt {TEAM}", "a/b/c/z.txt"))
        self.assertFalse(self.owned(f"/a/*/z.txt {TEAM}", "a/b/c/z.txt"))
        self.assertTrue(self.owned(f"/a/** {TEAM}", "a/b/c"))

    def test_the_last_matching_line_wins(self) -> None:
        text = f"*.md {TEAM}\n/docs/x.md\n"
        self.assertFalse(self.owned(text, "docs/x.md"))
        self.assertTrue(self.owned(text, "other.md"))

    def test_a_line_with_no_owner_releases_the_path(self) -> None:
        self.assertFalse(self.owned(f"/d/ {TEAM}\n/d/free.md\n", "d/free.md"))

    def test_a_path_matching_no_line_is_not_owned(self) -> None:
        self.assertFalse(self.owned(f"*.py {TEAM}", "README.md"))

    def test_comments_and_trailing_comments_are_ignored(self) -> None:
        text = f"# note\n*.py {TEAM} # why\n"
        self.assertEqual((TEAM,), co.owners_of(co.parse(text), "a.py"))

    def test_the_count_is_owned_over_total(self) -> None:
        rules = co.parse(f"*.py {TEAM}\n")
        self.assertEqual((1, 3), co.count(rules, ["a.py", "b.md", "c/d.txt"]))

    def test_an_unsupported_pattern_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            co.parse(f"!x {TEAM}")


if __name__ == "__main__":
    unittest.main()

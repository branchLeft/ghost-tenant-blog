"""Tests for the branchLeft blog theme package and its token use."""

from __future__ import annotations

import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

import build_theme

TOKEN_DEF: re.Pattern[str] = re.compile(r"(--bl-[a-z0-9-]+)\s*:")
TOKEN_USE: re.Pattern[str] = re.compile(r"var\((--bl-[a-z0-9-]+)")


def _defined_tokens() -> set[str]:
    text = (build_theme.THEME_DIR / "assets/css/tokens.css").read_text(encoding="utf-8")
    return set(TOKEN_DEF.findall(text))


def _used_tokens() -> set[str]:
    used: set[str] = set()
    for path in build_theme.THEME_DIR.rglob("*.css"):
        if "dist" in path.parts:
            continue
        used.update(TOKEN_USE.findall(path.read_text(encoding="utf-8")))
    return used


class ThemeTests(unittest.TestCase):
    def test_package_declares_ghost_engine(self) -> None:
        manifest = json.loads((build_theme.THEME_DIR / "package.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["name"])
        self.assertTrue(manifest["version"])
        self.assertTrue(manifest["engines"]["ghost"].startswith(">="))

    def test_every_used_token_is_defined(self) -> None:
        undefined = _used_tokens() - _defined_tokens()
        self.assertEqual(set(), undefined)

    def test_vendored_tokens_record_their_source(self) -> None:
        header = (build_theme.THEME_DIR / "assets/css/tokens.css").read_text(encoding="utf-8")
        self.assertIn("cf78f4da2d37", header.splitlines()[0])

    def test_build_zips_exactly_the_required_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "theme.zip"
            build_theme.build(build_theme.THEME_DIR, out)
            with zipfile.ZipFile(out) as archive:
                self.assertEqual(set(build_theme.REQUIRED_FILES), set(archive.namelist()))

    def test_build_refuses_an_incomplete_theme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "package.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                build_theme.build(theme, theme / "out.zip")


if __name__ == "__main__":
    unittest.main()

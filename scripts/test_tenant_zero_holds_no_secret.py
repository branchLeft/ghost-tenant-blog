#!/usr/bin/env python3
"""This tenant's stack holds no secret value.

Four facts, each a file in this checkout: the component is pinned at the
release that takes no secret, the program reads no secret and passes none, the
committed stack config has no secret in it, and the detector that decides the
last one can say yes. See test_tenant_zero_holds_no_secret.md.
"""

import importlib.util
import json
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
GUARD = ROOT / "scripts" / "assert-no-secure-stack-config.py"

# The first component release that takes no secret and exposes none.
SECRETLESS_COMPONENT = "8.0.0"
COMPONENT = "@branchleft/ghost-platform-tenant"

# What a program that holds or passes a secret has to contain. Matched on code
# with the comments taken out, so a sentence explaining the rule is not a hit.
SECRET_READS = re.compile(
    r"requireSecret|getSecret|requireSecretObject|getSecretObject|pulumi\s*\.\s*secret\s*\(|"
    r"\bsecrets\s*:|\bsecretsEnvFile\b|\bownerEmail\b"
)
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
LINE_COMMENT = re.compile(r"(?m)(?<![:\"'`])//.*$")

PROGRAM_FILES = ("config.ts", "index.ts")


def _load_guard():
    """Import the stack-config guard by path: its filename has hyphens."""
    spec = importlib.util.spec_from_file_location("assert_no_secure_stack_config", GUARD)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


guard = _load_guard()


def code_only(source: str) -> str:
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub("", source))


def secret_reads(source: str) -> list[str]:
    return sorted({match.group(0) for match in SECRET_READS.finditer(code_only(source))})


def stack_configs() -> list[pathlib.Path]:
    return sorted(ROOT.glob("Pulumi.*.yaml"))


class TheCommittedStackHoldsNoSecret(unittest.TestCase):
    def test_there_is_a_stack_config_to_check(self):
        self.assertTrue(stack_configs(), "no Pulumi.<stack>.yaml found, so the check below proves nothing")

    def test_no_stack_config_holds_a_secret(self):
        for path in stack_configs():
            with self.subTest(path=path.name):
                findings = guard.offending_lines(path.read_text(encoding="utf-8"))
                self.assertEqual(findings, [], f"{path.name} holds a secret at the lines listed")


class TheProgramReadsAndPassesNoSecret(unittest.TestCase):
    def test_the_component_is_pinned_at_the_release_that_takes_no_secret(self):
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["dependencies"][COMPONENT], SECRETLESS_COMPONENT)

    def test_no_program_file_reads_or_passes_a_secret(self):
        for name in PROGRAM_FILES:
            with self.subTest(file=name):
                self.assertEqual(secret_reads((ROOT / name).read_text(encoding="utf-8")), [])


class TheDetectorCanSaySo(unittest.TestCase):
    """An empty list above only means something if the detector can be non-empty."""

    def test_a_secret_read_is_found(self):
        self.assertEqual(secret_reads("const p = config.requireSecret('x');"), ["requireSecret"])

    def test_a_secret_object_read_is_found(self):
        self.assertTrue(secret_reads("config.getSecretObject('x')"))

    def test_a_pulumi_secret_wrapper_is_found(self):
        self.assertTrue(secret_reads("const s = pulumi.secret(v);"))

    def test_a_secrets_argument_is_found(self):
        self.assertTrue(secret_reads("new GhostTenant(slug, { descriptor, secrets: { a: b } });"))

    def test_the_removed_output_is_found(self):
        self.assertTrue(secret_reads("export const f = tenant.secretsEnvFile;"))

    def test_a_comment_that_names_one_is_not_a_read(self):
        source = "// never requireSecret here\n/* nor secrets: {} */\nconst a = 1;\n"
        self.assertEqual(secret_reads(source), [])

    def test_a_url_in_code_is_not_taken_for_a_comment(self):
        self.assertEqual(secret_reads("const u = 'https://x.example'; config.requireSecret('k');"), ["requireSecret"])

    def test_the_guard_flags_a_secure_entry_in_a_stack_config(self):
        self.assertTrue(guard.offending_lines("config:\n  p:k:\n    secure: FAKE-CIPHERTEXT\n"))


if __name__ == "__main__":
    unittest.main()

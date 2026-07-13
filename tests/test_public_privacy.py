from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

ALLOWED_PROFILE_PREFIXES = {
    "profiles/demo-jordan-lee/",
}

BLOCKED_PATH_PREFIXES = (
    "input/raw/",
    "input/test_month/",
    "output/",
    "venv/",
)

BLOCKED_PATH_SUFFIXES = (
    ".DS_Store",
    ".pdf",
    ".xlsx",
    ".xls",
    ".xlsm",
)

BLOCKED_EXACT_PATHS = {
    "input/template/accounts.csv",
}

SECRET_PATTERNS = {
    "absolute user path": re.compile(r"/" + "Users" + r"/[^/\s]+"),
    "email address": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "us social security number": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "github token": re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"),
    "aws access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def is_allowed_profile_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in ALLOWED_PROFILE_PREFIXES)


class PublicPrivacyTests(unittest.TestCase):
    def test_tracked_paths_do_not_include_private_or_generated_files(self) -> None:
        violations: list[str] = []
        for path in tracked_files():
            if path in BLOCKED_EXACT_PATHS:
                violations.append(path)
                continue
            if path.startswith("profiles/") and not is_allowed_profile_path(path):
                violations.append(path)
                continue
            if path.startswith(BLOCKED_PATH_PREFIXES):
                violations.append(path)
                continue
            if path.endswith(BLOCKED_PATH_SUFFIXES):
                violations.append(path)

        self.assertEqual(violations, [], "Tracked private/generated paths should not be public")

    def test_tracked_text_does_not_include_sensitive_markers(self) -> None:
        blocked_terms = [
            re.compile(r"\b" + re.escape("JPM" + "ORGAN") + r"\b", re.IGNORECASE),
            re.compile(r"\b" + re.escape("Cha" + "se") + r"\b", re.IGNORECASE),
            re.compile(r"\b" + re.escape("gl" + "ai") + r"\b", re.IGNORECASE),
        ]
        violations: list[str] = []

        for path in tracked_files():
            file_path = REPO_ROOT / path
            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            for pattern in blocked_terms:
                if pattern.search(content):
                    violations.append(f"{path}: blocked term")
                    break

            for label, pattern in SECRET_PATTERNS.items():
                if pattern.search(content):
                    violations.append(f"{path}: {label}")
                    break

        self.assertEqual(violations, [], "Tracked text should not include private markers or secrets")


if __name__ == "__main__":
    unittest.main()

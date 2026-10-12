#!/usr/bin/env python3
"""Fail if sanitized n8n fields reappear anywhere in the repo."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Directories that are never scanned.
EXCLUDE_DIRS = {".git", ".ruff_cache"}

# This file is the one place that must spell out the forbidden key names and
# the n8n instance-id shape, so it skips itself by exact path. Personal
# identifiers are handled separately by .gitleaks.toml.
EXCLUDE_FILES = {Path(__file__).resolve()}

# Keys that must not exist in a committed workflow export.
FORBIDDEN_KEYS = ("webhookId", "credentials", "instanceId")

# The n8n instance id is a 64 character hex string.
HEX64 = re.compile(r"\b[a-f0-9]{64}\b", re.IGNORECASE)


def iter_files() -> list[Path]:
    # A directory we cannot list must fail the scan, not be skipped.
    def fail_on_error(exc: OSError) -> None:
        raise exc

    files: list[Path] = []
    for root, dirnames, filenames in os.walk(ROOT, onerror=fail_on_error):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for name in filenames:
            path = Path(root) / name
            parts = path.relative_to(ROOT).parts
            if any(part in EXCLUDE_DIRS for part in parts):
                continue
            if path.resolve() in EXCLUDE_FILES:
                continue
            if path.is_file():
                files.append(path)
    return sorted(files)


def scan_file(path: Path) -> list[str]:
    # Non-UTF-8 files are binary assets (the committed PNG under assets/)
    # and out of scope: a decode error is a deliberate skip. Any other
    # read failure is an OSError and propagates, failing the scan.
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    relative = path.relative_to(ROOT)
    findings: list[str] = []
    for number, line in enumerate(text.splitlines(), 1):
        prefix = f"{relative}:{number}: "
        for key in FORBIDDEN_KEYS:
            if f'"{key}"' in line:
                findings.append(f'{prefix}forbidden key "{key}"')
        if HEX64.search(line):
            message = f"{prefix}64-char hex string looks like an instance id"
            findings.append(message)
    return findings


def main() -> int:
    findings: list[str] = []
    for path in iter_files():
        findings.extend(scan_file(path))

    if findings:
        for finding in findings:
            print(f"FAIL: {finding}")
        return 1

    print("OK: no sanitized n8n fields found")
    return 0


if __name__ == "__main__":
    sys.exit(main())

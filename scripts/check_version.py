"""Checks that a pull request keeps the app version consistent and bumps it.

The version lives in frontend/package.json, frontend/package-lock.json and
the newest entry of frontend/src/data/changelog.ts. All three must agree, and
a PR that changes shipped code must raise the version above the base branch.

Usage: python3 scripts/check_version.py <base-ref> [--skip-bump]
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

PACKAGE = "frontend/package.json"
LOCK = "frontend/package-lock.json"
CHANGELOG = "frontend/src/data/changelog.ts"

# Paths whose changes reach users, so they need a new version.
SHIPPED = (
    "backend/app/",
    "backend/requirements.txt",
    "backend/Dockerfile",
    "backend/sample-docs/",
    "frontend/src/",
    "frontend/public/",
    "frontend/index.html",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/Dockerfile",
    "frontend/nginx",
    "frontend/vite.config.ts",
    "docker-compose",
    "start.sh",
    "stop.sh",
    "scripts/vectorstore_maintenance.py",
)

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
CHANGELOG_VERSION = re.compile(r"version:\s*'([^']+)'")


def git_show(ref: str, path: str) -> str:
    return subprocess.run(
        ["git", "show", f"{ref}:{path}"], check=True, capture_output=True, text=True
    ).stdout


def versions(read) -> dict[str, str]:
    lock = json.loads(read(LOCK))
    match = CHANGELOG_VERSION.search(read(CHANGELOG))
    return {
        PACKAGE: json.loads(read(PACKAGE))["version"],
        f"{LOCK} (root)": lock["version"],
        f"{LOCK} (packages)": lock["packages"][""]["version"],
        f"{CHANGELOG} (newest entry)": match.group(1) if match else "<missing>",
    }


def parse(version: str) -> tuple[int, int, int]:
    m = SEMVER.match(version)
    if not m:
        raise ValueError(version)
    return (int(m[1]), int(m[2]), int(m[3]))


def changed_files(base: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [line for line in out.splitlines() if line]


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    base = sys.argv[1]
    skip_bump = "--skip-bump" in sys.argv[2:]
    errors: list[str] = []

    def read_head(path: str) -> str:
        with open(path, encoding="utf-8") as f:
            return f.read()

    head = versions(read_head)
    version = head[PACKAGE]
    for where, value in head.items():
        if value != version:
            errors.append(f"{where} is {value}, but {PACKAGE} is {version}.")
    try:
        parse(version)
    except ValueError:
        errors.append(f"{version} is not a MAJOR.MINOR.PATCH version.")

    shipped = [f for f in changed_files(base) if f.startswith(SHIPPED)]
    base_version = json.loads(git_show(base, PACKAGE))["version"]
    if not shipped:
        print("No shipped files changed, so no version bump is required.")
    elif skip_bump:
        print("The skip-version label is set, so the bump check is skipped.")
    elif not errors and parse(version) <= parse(base_version):
        errors.append(
            f"Shipped files changed (e.g. {shipped[0]}), so the version must go "
            f"above {base_version}. Bump {PACKAGE} with `npm version <x.y.z> "
            f"--no-git-tag-version` and add a {CHANGELOG} entry, or add the "
            "skip-version label."
        )

    for error in errors:
        print(f"::error::{error}")
    if not errors:
        print(f"Version {version} is consistent (base {base_version}).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

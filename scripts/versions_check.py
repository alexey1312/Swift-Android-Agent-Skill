#!/usr/bin/env python3
"""Compare the pins in references/versions.md with the latest upstream releases.

The first ```json block in references/versions.md is a flat object of pins, e.g.

    {"checked": "2026-10-01", "swift-release": "6.4.0", "skip-release": "1.9.12", "swift-java-release": "0.6.0"}

Known pins and where their latest value comes from:

    swift-release                 swift.org install API, newest release name
    swift-android-sdk-checksum    swift.org install API, Android SDK checksum of that release
    skip-release                  GitHub releases, skiptools/skip
    swift-java-release            GitHub releases, swiftlang/swift-java
    swiftly-release               GitHub releases, swiftlang/swiftly
    swift-android-action-release  GitHub releases, skiptools/swift-android-action

`checked` is the date of the last manual check and is only reported; other keys are
listed as "not checked". GITHUB_TOKEN, when set, is sent to api.github.com only.

    python3 scripts/versions_check.py                   # live lookups
    python3 scripts/versions_check.py --offline FILE    # canned responses: {"<url>": <JSON body>, ...}

Prints a Markdown table. Exit status: 0 every pin is current, 1 a pin moved,
2 versions.md or its JSON block is missing or malformed, 3 a lookup failed and nothing moved.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "references" / "versions.md"
SWIFT_RELEASES = "https://www.swift.org/api/v1/install/releases.json"
GITHUB_LATEST = "https://api.github.com/repos/{repo}/releases/latest"
GITHUB_PINS = {
    "skip-release": "skiptools/skip",
    "swift-java-release": "swiftlang/swift-java",
    "swiftly-release": "swiftlang/swiftly",
    "swift-android-action-release": "skiptools/swift-android-action",
}
SWIFT_PINS = ("swift-release", "swift-android-sdk-checksum")
NOT_PINS = {"checked"}
JSON_BLOCK = re.compile(r"^```json[ \t]*\n(.*?)^```", re.S | re.M)
TIMEOUT = 20

Fetch = Callable[[str], object]


class PinsError(Exception):
    """versions.md or its JSON block is missing or malformed."""


def read_pins(path: Path = VERSIONS) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise PinsError(f"{path} not found; it should hold the pins in its first ```json block") from None
    match = JSON_BLOCK.search(text)
    if not match:
        raise PinsError(f"{path} has no ```json block; the first one must hold the pins")
    try:
        pins = json.loads(match.group(1))
    except json.JSONDecodeError as error:
        raise PinsError(f"the first ```json block in {path} does not parse: {error}") from None
    if not isinstance(pins, dict) or not pins or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in pins.items()
    ):
        raise PinsError(f"the first ```json block in {path} must be a flat object of string pins")
    return pins


def version_key(version: str) -> tuple[int, ...] | None:
    """6.4 and 6.4.0 compare equal; a leading v is ignored; None when not numeric."""
    match = re.fullmatch(r"v?(\d+(?:\.\d+)*)", version.strip())
    if not match:
        return None
    numbers = [int(part) for part in match.group(1).split(".")]
    while len(numbers) < 3:
        numbers.append(0)
    return tuple(numbers)


def same_version(pinned: str, latest: str) -> bool:
    pinned_key, latest_key = version_key(pinned), version_key(latest)
    if pinned_key is not None and latest_key is not None:
        return pinned_key == latest_key
    return pinned.strip().lstrip("v") == latest.strip().lstrip("v")


def latest_swift_release(releases: object) -> dict:
    if not isinstance(releases, list):
        raise ValueError("releases.json is not a list")
    named = [release for release in releases if isinstance(release, dict) and version_key(str(release.get("name", "")))]
    if not named:
        raise ValueError("releases.json lists no numbered release")
    return max(named, key=lambda release: version_key(str(release["name"])))


def android_checksum(release: dict) -> str:
    for entry in release.get("platforms", []):
        if isinstance(entry, dict) and entry.get("platform") == "android-sdk" and entry.get("checksum"):
            return str(entry["checksum"])
    raise ValueError(f"Swift {release.get('name')} lists no Android SDK checksum")


def request_for(url: str, env: Mapping[str, str] = os.environ) -> urllib.request.Request:
    headers = {"User-Agent": "swift-android-versions-check"}
    if url.startswith("https://api.github.com/"):
        headers["Accept"] = "application/vnd.github+json"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
        if env.get("GITHUB_TOKEN"):
            headers["Authorization"] = f"Bearer {env['GITHUB_TOKEN']}"
    return urllib.request.Request(url, headers=headers)


def fetch_live(url: str) -> object:
    with urllib.request.urlopen(request_for(url), timeout=TIMEOUT) as response:
        return json.load(response)


def fetch_offline(path: Path) -> Fetch:
    responses = json.loads(path.read_text(encoding="utf-8"))

    def fetch(url: str) -> object:
        if url not in responses:
            raise LookupError(f"no canned response for {url}")
        return responses[url]

    return fetch


def check(pins: Mapping[str, str], fetch: Fetch) -> list[dict]:
    """One row per pin: pin, pinned, latest, status (current, moved, not checked, error)."""
    cache: dict[str, object] = {}

    def get(url: str) -> object:
        if url not in cache:
            cache[url] = fetch(url)
        return cache[url]

    rows = []
    for pin, pinned in pins.items():
        if pin in NOT_PINS:
            continue
        row = {"pin": pin, "pinned": pinned, "latest": None, "status": "not checked", "source": None}
        try:
            if pin in SWIFT_PINS:
                row["source"] = SWIFT_RELEASES
                release = latest_swift_release(get(SWIFT_RELEASES))
                row["latest"] = str(release["name"]) if pin == "swift-release" else android_checksum(release)
            elif pin in GITHUB_PINS:
                row["source"] = GITHUB_LATEST.format(repo=GITHUB_PINS[pin])
                body = get(row["source"])
                if not isinstance(body, dict) or not body.get("tag_name"):
                    raise ValueError("no tag_name in the latest release")
                row["latest"] = str(body["tag_name"])
            else:
                rows.append(row)
                continue
        except (OSError, ValueError, LookupError, urllib.error.URLError) as error:
            row["status"] = f"error: {error}"
            rows.append(row)
            continue
        if pin == "swift-android-sdk-checksum":
            row["status"] = "current" if pinned.strip() == row["latest"] else "moved"
        else:
            row["status"] = "current" if same_version(pinned, row["latest"]) else "moved"
        rows.append(row)
    return rows


def markdown(rows: list[dict], pins: Mapping[str, str], path: Path) -> str:
    try:
        shown = path.relative_to(ROOT)
    except ValueError:
        shown = path
    lines = ["## Version pins", ""]
    lines.append(f"From `{shown}`" + (f", last checked by hand on {pins['checked']}." if "checked" in pins else "."))
    lines += ["", "| Pin | Pinned | Latest | Status |", "| --- | --- | --- | --- |"]
    for row in rows:
        status = f"**{row['status']}**" if row["status"] == "moved" else row["status"]
        latest = f"`{row['latest']}`" if row["latest"] else ""
        lines.append(f"| `{row['pin']}` | `{row['pinned']}` | {latest} | {status.replace('|', '/')} |")
    moved = [row["pin"] for row in rows if row["status"] == "moved"]
    if moved:
        lines += ["", f"Moved: {', '.join(moved)}. Re-check the sources, then update references/versions.md "
                      "and every place the old value is pinned."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--versions", type=Path, default=VERSIONS, help="versions file (default: %(default)s)")
    parser.add_argument("--offline", type=Path, metavar="FILE", help="read canned upstream responses from FILE")
    args = parser.parse_args(argv)
    try:
        pins = read_pins(args.versions)
    except PinsError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    fetch = fetch_offline(args.offline) if args.offline else fetch_live
    rows = check(pins, fetch)
    sys.stdout.write(markdown(rows, pins, args.versions))
    if any(row["status"] == "moved" for row in rows):
        return 1
    if any(row["status"].startswith("error") for row in rows):
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

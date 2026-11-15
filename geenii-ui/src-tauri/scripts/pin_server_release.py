#!/usr/bin/env python3
"""Pin the geenii server release the desktop app downloads.

Fetches the published .sha256 files of a GitHub release and writes the version
and checksums into server-release.json. Commit the result: the app only installs
an archive whose SHA-256 matches the pinned value.

Usage: python3 scripts/pin_server_release.py v0.4.0.dev4
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

MANIFEST = Path(__file__).resolve().parent.parent / "server-release.json"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "geenii-pin-server-release"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode()


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    version = sys.argv[1]
    manifest = json.loads(MANIFEST.read_text())

    checksums = {}
    for target in manifest["sha256"]:
        url = manifest["url"].format(version=version, target=target) + ".sha256"
        try:
            text = fetch(url)
        except Exception as exc:  # noqa: BLE001 - report and continue
            print(f"{target}: not found ({exc}); left empty", file=sys.stderr)
            checksums[target] = ""
            continue
        digest = text.split()[0].lower() if text.strip() else ""
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            print(f"{target}: unexpected checksum file content: {text!r}", file=sys.stderr)
            return 1
        checksums[target] = digest
        print(f"{target}: {digest}")

    manifest["version"] = version
    manifest["sha256"] = checksums
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"updated {MANIFEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

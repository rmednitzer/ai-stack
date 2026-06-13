#!/usr/bin/env python3
"""Enforce that every Grype CVE exception in .grype.yaml is time-boxed.

The cve-scan job (B4 / ADR-014) is a *blocking* gate: a critical CVE fails the
build. The only relief valve is an ``ignore:`` entry in ``.grype.yaml`` for a
critical with no available fix. To stop such an exception becoming a permanent,
forgotten hole, every entry must carry an ``expires: YYYY-MM-DD`` (UTC) token in
a comment on a line preceding its ``- vulnerability:`` line. This guard fails
when an exception is missing that token, has a malformed date, or is past it.

Grype itself ignores the comments; this guard is the policy layer over them.
See docs/operations/hardening-guide.md.
"""

from __future__ import annotations

import datetime
import pathlib
import re
import sys

CONFIG = pathlib.Path(".grype.yaml")
EXPIRES_RE = re.compile(r"expires:\s*(\d{4}-\d{2}-\d{2})")
ENTRY_RE = re.compile(r"^\s*-\s*vulnerability:\s*(\S+)")


def main() -> int:
    if not CONFIG.is_file():
        # No config means no exceptions, so there is nothing to enforce.
        print(f"{CONFIG}: not present; no CVE exceptions to check.")
        return 0

    today = datetime.datetime.now(datetime.timezone.utc).date()
    errors: list[str] = []
    pending_expiry: str | None = None

    for raw in CONFIG.read_text(encoding="utf-8").splitlines():
        found = EXPIRES_RE.search(raw)
        if found:
            pending_expiry = found.group(1)
        entry = ENTRY_RE.match(raw)
        if entry:
            cve = entry.group(1)
            if pending_expiry is None:
                errors.append(f"{cve}: missing 'expires: YYYY-MM-DD' annotation")
            else:
                try:
                    expiry = datetime.date.fromisoformat(pending_expiry)
                except ValueError:
                    errors.append(f"{cve}: malformed expires date {pending_expiry!r}")
                else:
                    if expiry < today:
                        errors.append(f"{cve}: exception expired {pending_expiry}")
            pending_expiry = None

    if errors:
        for err in errors:
            print(f"::error::grype CVE exception {err}")
        print(
            f"\n{len(errors)} expired/invalid CVE exception(s) in {CONFIG}. "
            "Bump the affected image, or renew the exception with a future "
            "expiry and a linked advisory."
        )
        return 1

    print(f"{CONFIG}: all CVE exceptions are time-boxed and current.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

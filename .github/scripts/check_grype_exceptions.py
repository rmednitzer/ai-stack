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
        # The cve-scan job passes `--config .grype.yaml`, so a missing file is a
        # misconfiguration, not "no exceptions". Fail fast with a clear message
        # rather than letting grype fail later with an opaque one.
        print(f"::error::{CONFIG} is missing (the cve-scan job requires it).")
        return 1

    today = datetime.datetime.now(datetime.timezone.utc).date()
    errors: list[str] = []
    # The expiry that applies to the next entry. Only a comment grouped directly
    # above a `- vulnerability:` entry can set it; a blank or structural line
    # clears it, so an `expires:` from an unrelated block (e.g. the documentation
    # example in the header) cannot leak onto a later real entry.
    pending_expiry: str | None = None

    for raw in CONFIG.read_text(encoding="utf-8").splitlines():
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
        elif raw.lstrip().startswith("#"):
            found = EXPIRES_RE.search(raw)
            if found:
                pending_expiry = found.group(1)
        else:
            # Blank line, the `ignore:` key, or any other structural line breaks
            # the comment-to-entry grouping.
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

#!/usr/bin/env python
"""Ensure an Argos Translate language pair is installed (idempotent).

Usage:
    python scripts/ensure_argos_pair.py <from> <to>   # e.g. en es

Exits 0 if the pair is already installed or was installed successfully; exits 1
(with a message) if the package could not be installed — e.g. offline and not
cached — so callers (the Makefile / CI) can decide whether to skip the
real-translation E2E tests.
"""

from __future__ import annotations

import sys


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <from_code> <to_code>", file=sys.stderr)
        return 2
    from_code, to_code = sys.argv[1], sys.argv[2]

    import argostranslate.package as pkg
    import argostranslate.translate as translate

    def installed() -> bool:
        try:
            return translate.get_translation_from_codes(from_code, to_code) is not None
        except Exception:
            return False

    if installed():
        print(f"Argos {from_code}->{to_code} already installed")
        return 0

    try:
        pkg.update_package_index()
        pkg.install_package_for_language_pair(from_code, to_code)
    except Exception as exc:  # offline / unavailable
        print(f"could not install Argos {from_code}->{to_code}: {exc}", file=sys.stderr)
        return 1

    if installed():
        print(f"installed Argos {from_code}->{to_code}")
        return 0

    print(f"Argos {from_code}->{to_code} still unavailable after install attempt", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

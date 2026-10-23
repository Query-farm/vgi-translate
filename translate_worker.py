# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "vgi-python[http]>=0.46.1",
#     "argostranslate>=1.9",
#     "py3langid>=0.4",
# ]
# ///
"""Repo-root stdio entry for the vgi-translate worker (thin PEP 723 shim).

The catalog, :class:`TranslateWorker`, and :func:`main` now live in the
wheel-importable ``vgi_translate.worker`` module so the published wheel actually
contains the worker. This shim re-exports them and stays the on-disk entry that
``uv run translate_worker.py`` (Makefile, ci/run-integration.sh, tests) spawns —
the PEP 723 inline metadata lets ``uv run`` resolve the deps without an install.

Usage:
    uv run translate_worker.py                # serve over stdio (DuckDB subprocess)
    uv run translate_worker.py --http --port 0 --port-file /tmp/p   # HTTP server

    INSTALL vgi FROM community; LOAD vgi;
    ATTACH 'tr' (TYPE vgi, LOCATION 'uv run translate_worker.py');

    SELECT tr.translate('Hello, world.', 'es');
"""

from __future__ import annotations

from vgi_translate.worker import TranslateWorker, main

__all__ = ["TranslateWorker", "main"]


if __name__ == "__main__":
    main()

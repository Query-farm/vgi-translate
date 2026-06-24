# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "vgi-python[http]>=0.8.3",
#     "argostranslate>=1.9",
#     "py3langid>=0.3",
# ]
# ///
"""VGI worker exposing local neural machine translation to DuckDB/SQL.

Assembles the implementation modules in ``vgi_translate`` into a single
``translate`` catalog and runs the worker over stdio (a DuckDB subprocess).

Usage:
    uv run translate_worker.py          # serve over stdio (DuckDB subprocess)

    INSTALL vgi FROM community; LOAD vgi;
    ATTACH 'tr' (TYPE vgi, LOCATION 'uv run translate_worker.py');

    SELECT tr.translate('Hello, world.', 'es');
    SELECT tr.detect_lang('Bonjour le monde');
    SELECT * FROM tr.translate_all((SELECT id, body FROM messages),
                                   id := 'id', target := 'es', source := 'auto');

Default backend: **Argos Translate** (MIT), which downloads permissively-
licensed OPUS-MT language packages on demand. See README.md for the licensing
rationale and the NLLB-200 (CC-BY-NC) caveat, and ``VGI_TRANSLATE_BACKEND`` to
opt into another backend.
"""

from __future__ import annotations

from vgi import Worker
from vgi.catalog import Catalog, Schema

from vgi_translate.scalars import SCALAR_FUNCTIONS
from vgi_translate.tables import TABLE_FUNCTIONS

_FUNCTIONS: list[type] = [*SCALAR_FUNCTIONS, *TABLE_FUNCTIONS]

_TRANSLATE_CATALOG = Catalog(
    name="translate",
    default_schema="main",
    schemas=[
        Schema(
            name="main",
            comment="Local neural machine translation and language detection for SQL",
            functions=list(_FUNCTIONS),
        ),
    ],
)


class TranslateWorker(Worker):
    """Worker process hosting the translation catalog."""

    catalog = _TRANSLATE_CATALOG


def main() -> None:
    """Run the translation worker process over stdio."""
    TranslateWorker.main()


if __name__ == "__main__":
    main()

# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "vgi-python[http]>=0.8.4",
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

_REPO_URL = "https://github.com/Query-farm/vgi-translate"

_TRANSLATE_CATALOG = Catalog(
    name="translate",
    default_schema="main",
    comment="Local neural machine translation and language detection for DuckDB/SQL.",
    tags={
        "vgi.description_llm": (
            "Translate text between languages and detect the language of text, fully "
            "offline using local neural machine-translation models (Argos Translate / "
            "OPUS-MT). Provides scalar functions to translate a string into a target "
            "language (with optional explicit source) and to detect a string's ISO 639-1 "
            "language code, plus a batched table function to translate a whole table of "
            "rows while carrying an id column through. No API keys, no network at query "
            "time once a language package is cached. Use for in-SQL machine translation "
            "and language identification."
        ),
        "vgi.description_md": (
            "# translate\n\n"
            "Local neural machine translation and language detection over Apache Arrow.\n\n"
            "Scalars: `translate(text, target)`, `translate(text, target, source)`, "
            "`detect_lang(text)`. Table: `translate_all(rows, id, target, source)`.\n\n"
            "Default backend is **Argos Translate** (MIT; OPUS-MT models), so it is "
            "commercial-safe and runs fully offline."
        ),
        "vgi.author": "Query.Farm",
        "vgi.copyright": "Copyright 2026 Query Farm LLC - https://query.farm",
        "vgi.license": "Query Farm Source-Available License, Version 1.0",
        "vgi.support_contact": f"{_REPO_URL}/issues",
        "vgi.support_policy_url": f"{_REPO_URL}/blob/main/README.md",
    },
    source_url=_REPO_URL,
    schemas=[
        Schema(
            name="main",
            comment="Local neural machine translation and language detection for SQL.",
            tags={
                "vgi.description_llm": (
                    "Machine-translation and language-detection functions: translate text "
                    "into a target language (source auto-detected or explicit), detect the "
                    "ISO 639-1 language code of text, and translate a streamed table of "
                    "rows in batch with an id passthrough column."
                ),
                "vgi.description_md": ("Machine-translation and language-detection functions over Apache Arrow."),
            },
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

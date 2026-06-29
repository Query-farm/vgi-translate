# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "vgi-python[http]>=0.8.8",
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

import json

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
        "vgi.title": "Local Machine Translation & Language Detection",
        "vgi.keywords": json.dumps(
            [
                "translate",
                "translation",
                "machine translation",
                "neural machine translation",
                "NMT",
                "language detection",
                "detect language",
                "language identification",
                "ISO 639-1",
                "Argos Translate",
                "OPUS-MT",
                "offline translation",
                "multilingual",
                "localization",
                "i18n",
            ]
        ),
        "vgi.doc_llm": (
            "Translate text between languages and detect the language of text, fully "
            "offline using local neural machine-translation models (Argos Translate / "
            "OPUS-MT). Provides scalar functions to translate a string into a target "
            "language (with optional explicit source) and to detect a string's ISO 639-1 "
            "language code, plus a batched table function to translate a whole table of "
            "rows while carrying an id column through. No API keys, no network at query "
            "time once a language package is cached. Use for in-SQL machine translation "
            "and language identification."
        ),
        "vgi.doc_md": (
            "# Offline Machine Translation & Language Detection in SQL\n\n"
            "Translate text between languages and identify the language of any string "
            "directly in DuckDB SQL — fully offline, with no API keys, no rate limits, "
            "and no data ever leaving your machine. This VGI extension brings local "
            "**neural machine translation (NMT)** and **language detection** to your "
            "queries, so multilingual text processing, localization (i18n), and "
            "content normalization become ordinary SQL.\n\n"
            "Translation is powered by [Argos Translate]"
            "(https://github.com/argosopentech/argos-translate) "
            "([project site & docs](https://www.argosopentech.com/)), an open-source "
            "(MIT-licensed) offline translation library built on the "
            "[OPUS-MT](https://github.com/Helsinki-NLP/Opus-MT) neural models trained on "
            "the [OPUS](https://opus.nlpl.eu/) parallel corpora. Language packages install "
            "lazily on first use and are cached per worker process, so a model loads once "
            "and then serves every subsequent query at full speed with zero network access. "
            "Because Argos Translate and the OPUS-MT models are permissively licensed, this "
            "default backend is **commercial-safe** (the CC-BY-NC NLLB-200 models are "
            "intentionally not the default). Language detection uses "
            "[py3langid](https://github.com/adbar/py3langid), a fast BSD-licensed "
            "identifier that ships its own model and runs entirely offline.\n\n"
            "The catalog exposes a small, focused function surface. The scalar "
            "`translate(text, target)` translates a string into an ISO 639-1 target "
            "language while auto-detecting the source per row, and the "
            "`translate(text, target, source)` overload lets you pin an explicit source "
            "language. `detect_lang(text)` returns the detected ISO 639-1 language code of "
            "each value. For high-throughput workloads, the table function "
            "`translate_all(rows, id, target, source)` streams a whole table of rows "
            "through the model in batches — reusing the cached model across the entire scan "
            "and carrying an `id` column through so results join straight back to the "
            "source. Typical uses include translating user-generated content, "
            "normalizing multilingual product catalogs and support tickets, building "
            "localization pipelines, and routing or filtering rows by detected language. "
            "Source, issues, and full documentation live in the "
            "[project repository](https://github.com/Query-farm/vgi-translate)."
        ),
        "vgi.author": "Query.Farm",
        "vgi.copyright": "Copyright 2026 Query Farm LLC - https://query.farm",
        "vgi.license": "LicenseRef-QueryFarm-Source-Available-1.0",
        "vgi.support_contact": f"{_REPO_URL}/issues",
        "vgi.support_policy_url": f"{_REPO_URL}/blob/main/README.md",
    },
    source_url=_REPO_URL,
    schemas=[
        Schema(
            name="main",
            comment="Local neural machine translation and language detection for SQL.",
            tags={
                "vgi.title": "Translate — main",
                "vgi.keywords": json.dumps(
                    [
                        "translate",
                        "detect_lang",
                        "translate_all",
                        "machine translation",
                        "language detection",
                        "ISO 639-1",
                        "multilingual",
                        "localization",
                        "NMT",
                    ]
                ),
                # VGI123 classifying tags use BARE keys (not vgi.-namespaced) for faceting.
                "domain": "natural-language-processing",
                "category": "translation",
                "topic": "machine-translation",
                "vgi.doc_llm": (
                    "Machine-translation and language-detection functions: translate text "
                    "into a target language (source auto-detected or explicit), detect the "
                    "ISO 639-1 language code of text, and translate a streamed table of "
                    "rows in batch with an id passthrough column."
                ),
                "vgi.doc_md": (
                    "Machine-translation and language-detection functions over Apache Arrow.\n\n"
                    "Use `translate` / `detect_lang` for per-row scalar work and "
                    "`translate_all` for high-throughput batch translation of a whole table."
                ),
                # VGI506 representative example queries for the schema (executed by the linter).
                "vgi.example_queries": (
                    "SELECT translate.main.translate('The quick brown fox jumps over the lazy dog.', 'es');\n"
                    "SELECT translate.main.translate('Hola, mundo.', 'en', 'es');\n"
                    "SELECT translate.main.detect_lang('Bonjour le monde');\n"
                    "SELECT * FROM translate.main.translate_all("
                    "(SELECT 1 AS id, 'The quick brown fox jumps over the lazy dog.' AS body), "
                    "id := 'id', target := 'es', source := 'en');"
                ),
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

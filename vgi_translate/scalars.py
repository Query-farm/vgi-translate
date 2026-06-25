"""Scalar translation functions: ``translate`` and ``detect_lang``.

``translate(text, to_lang)`` / ``translate(text, to_lang, from_lang)``
    Translate a string column into a target language. The 2-arg form detects the
    source per row; the 3-arg form takes an explicit ``from_lang`` (or ``'auto'``
    to detect). Returns VARCHAR.

``detect_lang(text)``
    Return the detected ISO 639-1 language code of each string. Returns VARCHAR.

A note on argument syntax
-------------------------
DuckDB *scalar* functions take **positional** arguments (the ``name := value``
named-argument syntax is a property of table functions and macros, not scalar
functions), and resolve overloads by arity. So the constant ``to_lang`` /
``from_lang`` arguments are positional, exposed as two overloads of ``translate``:

    SELECT translate(text, 'es');            -- source auto-detected
    SELECT translate(text, 'es', 'en');      -- explicit source language

The batched table function :class:`~vgi_translate.tables.TranslateAll` *does*
support the ``to := 'es'`` named-argument form (see ``tables.py``).

Models are loaded once per worker process and cached (see ``backend.py``); the
first call for a language pair lazily installs the Argos package.
"""

from __future__ import annotations

import json
from typing import Annotated

import pyarrow as pa
from vgi.arguments import ConstParam, Param, Returns
from vgi.metadata import FunctionExample
from vgi.scalar_function import ScalarFunction

from .backend import detect_language, get_backend
from .meta import object_tags

# VGI509 executable examples: self-contained, catalog-qualified SQL the linter
# runs against the attached worker. expected_result is omitted deliberately.
_EXECUTABLE_EXAMPLES = json.dumps(
    [
        {
            "description": "Translate an English sentence into Spanish (auto-detect source).",
            "sql": "SELECT translate.main.translate('The quick brown fox jumps over the lazy dog.', 'es') AS es",
        },
        {
            "description": "Translate a Spanish string back into English with an explicit source.",
            "sql": "SELECT translate.main.translate('Hola, mundo.', 'en', 'es') AS en",
        },
        {
            "description": "Detect the ISO 639-1 language code of a French phrase.",
            "sql": "SELECT translate.main.detect_lang('Bonjour le monde') AS lang",
        },
    ],
    indent=2,
)


def _translate_column(text: pa.StringArray, *, to_code: str, from_code: str) -> pa.StringArray:
    """Translate every string in a column, preserving NULLs."""
    backend = get_backend()
    out: list[str | None] = []
    for value in text.to_pylist():
        if value is None:
            out.append(None)
        else:
            out.append(backend.translate(value, to_code=to_code, from_code=from_code))
    return pa.array(out, type=pa.string())


# DuckDB scalar functions take positional arguments and resolve overloads by
# arity (not by name); the SDK's ConstParam has no default-value mechanism. So
# `translate` is provided as two arity overloads sharing the name "translate":
# a 2-arg form (auto-detect the source) and a 3-arg form (explicit source).


class TranslateAuto(ScalarFunction):
    """``translate(text, to_lang)`` — translate, auto-detecting the source language."""

    class Meta:
        """Function metadata."""

        name = "translate"
        description = "Translate text into a target language (source auto-detected) using a local neural model"
        categories = ["translation", "nlp"]
        examples = [
            FunctionExample(
                sql="SELECT translate.main.translate('The quick brown fox jumps over the lazy dog.', 'es')",
                description="Translate an English sentence to Spanish, detecting the source language",
            ),
        ]
        tags = {
            **object_tags(
                title="Translate Text (Auto-Detect Source)",
                doc_llm=(
                    "# translate (auto-detect source)\n\n"
                    "Translate a text value into a target language with a **local neural "
                    "machine-translation model**, automatically detecting the source "
                    "language per row. This is the two-argument overload "
                    "`translate(text, target)`; use the three-argument overload when you "
                    "already know the source language.\n\n"
                    "**Inputs**\n"
                    "- `text` (VARCHAR): the string to translate. `NULL` passes through as "
                    "`NULL`.\n"
                    "- `target` (VARCHAR constant): ISO 639-1 target language code, e.g. "
                    "`'es'`, `'fr'`, `'de'`.\n\n"
                    "**Output**: VARCHAR translated text.\n\n"
                    "**When to use**: translating short, free-form strings inline in SQL "
                    "when the source language is unknown or mixed. For large tables prefer "
                    "the `translate_all` table function, which loads the model once per "
                    "scan.\n\n"
                    "**Behavior & edge cases**: detection runs offline; the first call for "
                    "a language pair lazily installs the Argos package and caches it for "
                    "the worker process. Empty/whitespace input may detect as undetermined "
                    "and pass through largely unchanged."
                ),
                doc_md=(
                    "## translate(text, target)\n\n"
                    "Translate a string into `target`, **auto-detecting** the source "
                    "language. Powered by Argos Translate (MIT, OPUS-MT) and runs fully "
                    "offline once the language pair is cached.\n\n"
                    "### Usage\n\n"
                    "```sql\n"
                    "SELECT translate.main.translate('Hello, world.', 'es'); -- Hola, mundo.\n"
                    "```\n\n"
                    "### Notes\n\n"
                    "- `target` is an ISO 639-1 code such as `es`, `fr`, `de`.\n"
                    "- `NULL` input yields `NULL`.\n"
                    "- Use the three-argument overload to supply an explicit source, or "
                    "`translate_all` for batch throughput."
                ),
                keywords=[
                    "translate",
                    "translation",
                    "machine translation",
                    "auto-detect",
                    "neural",
                    "to spanish",
                    "to french",
                    "localize",
                    "localise",
                    "multilingual",
                    "NMT",
                ],
            ),
        }

    @classmethod
    def compute(
        cls,
        text: Annotated[pa.StringArray, Param(doc="Text to translate.")],
        to_lang: Annotated[str, ConstParam("Target language code, e.g. 'es' (ISO 639-1).")],
    ) -> Annotated[pa.StringArray, Returns()]:
        """Map each input row to its output value."""
        return _translate_column(text, to_code=to_lang, from_code="auto")


class Translate(ScalarFunction):
    """``translate(text, to_lang, from_lang)`` — translate with an explicit source.

    Pass ``from_lang := 'auto'`` (or use the 2-arg overload) to detect the
    source language per row. Uses the configured backend (Argos Translate by
    default).
    """

    class Meta:
        """Function metadata."""

        name = "translate"
        description = "Translate text from an explicit source language into a target language (local neural model)"
        categories = ["translation", "nlp"]
        examples = [
            FunctionExample(
                sql="SELECT translate.main.translate('Hola, mundo.', 'en', 'es')",
                description="Translate a known-Spanish string into English (returns 'Hello, world.')",
            ),
        ]
        tags = {
            **object_tags(
                title="Translate Text (Explicit Source)",
                doc_llm=(
                    "# translate (explicit source)\n\n"
                    "Translate a text value from a **known source language** into a target "
                    "language using a local neural machine-translation model. This is the "
                    "three-argument overload `translate(text, target, source)`.\n\n"
                    "**Inputs**\n"
                    "- `text` (VARCHAR): the string to translate. `NULL` passes through as "
                    "`NULL`.\n"
                    "- `target` (VARCHAR constant): ISO 639-1 target language code.\n"
                    "- `source` (VARCHAR constant): ISO 639-1 source language code, or "
                    "`'auto'` to detect per row.\n\n"
                    "**Output**: VARCHAR translated text.\n\n"
                    "**When to use**: prefer this overload when the source language is known "
                    "(skips detection and avoids mis-detection on short strings). Pass "
                    "`source := 'auto'` to fall back to detection. For large tables use the "
                    "`translate_all` table function instead.\n\n"
                    "**Behavior & edge cases**: the first call for a language pair lazily "
                    "installs and caches the Argos package; subsequent calls are offline."
                ),
                doc_md=(
                    "## translate(text, target, source)\n\n"
                    "Translate a string from an **explicit** `source` language into "
                    "`target`. Skips language detection, which is faster and more reliable "
                    "for short strings of a known language.\n\n"
                    "### Usage\n\n"
                    "```sql\n"
                    "SELECT translate.main.translate('Hola, mundo.', 'en', 'es'); -- Hello, world.\n"
                    "```\n\n"
                    "### Notes\n\n"
                    "- `source` / `target` are ISO 639-1 codes; pass `source := 'auto'` to "
                    "detect instead.\n"
                    "- `NULL` input yields `NULL`."
                ),
                keywords=[
                    "translate",
                    "translation",
                    "explicit source",
                    "from language",
                    "machine translation",
                    "neural",
                    "multilingual",
                    "NMT",
                    "localize",
                    "localise",
                ],
            ),
            "vgi.executable_examples": _EXECUTABLE_EXAMPLES,
        }

    @classmethod
    def compute(
        cls,
        text: Annotated[pa.StringArray, Param(doc="Text to translate.")],
        to_lang: Annotated[str, ConstParam("Target language code, e.g. 'es' (ISO 639-1).")],
        from_lang: Annotated[str, ConstParam("Source language code, or 'auto' to detect.")],
    ) -> Annotated[pa.StringArray, Returns()]:
        """Map each input row to its output value."""
        return _translate_column(text, to_code=to_lang, from_code=from_lang)


class DetectLang(ScalarFunction):
    """Detect the ISO 639-1 language code of each input string.

    Empty / whitespace-only input yields ``'und'`` (undetermined). Detection is
    fully offline (a bundled identification model), so it never downloads.
    """

    class Meta:
        """Function metadata."""

        name = "detect_lang"
        description = "Detect the ISO 639-1 language code of text"
        categories = ["translation", "nlp"]
        examples = [
            FunctionExample(
                sql="SELECT translate.main.detect_lang('Bonjour le monde')",
                description="Detect the language of a phrase (returns 'fr')",
            ),
            FunctionExample(
                sql="SELECT translate.main.detect_lang('Guten Morgen')",
                description="Detect the language of a German greeting (returns 'de')",
            ),
        ]
        tags = {
            **object_tags(
                title="Detect Text Language Code",
                doc_llm=(
                    "# detect_lang\n\n"
                    "Detect and return the **ISO 639-1 language code** of each input string "
                    "using a bundled, fully-offline language-identification model "
                    "(`py3langid`). No download, ever.\n\n"
                    "**Inputs**\n"
                    "- `text` (VARCHAR): the string whose language to identify. `NULL` "
                    "passes through as `NULL`.\n\n"
                    "**Output**: VARCHAR — a two-letter ISO 639-1 code such as `'en'`, "
                    "`'fr'`, `'de'`; empty/whitespace-only input yields `'und'` "
                    "(undetermined).\n\n"
                    "**When to use**: route, filter, or tag rows by language before "
                    "translating, or to populate a language column. Detection is per row "
                    "and most reliable on longer text; very short strings can be "
                    "ambiguous.\n\n"
                    "**Behavior & edge cases**: deterministic and offline; pair with "
                    "`translate` (passing the detected code as the source) for an "
                    "explicit-source translation pipeline."
                ),
                doc_md=(
                    "## detect_lang(text)\n\n"
                    "Return the **ISO 639-1** language code of a string using a bundled "
                    "offline identifier (`py3langid`, BSD). Never downloads.\n\n"
                    "### Usage\n\n"
                    "```sql\n"
                    "SELECT translate.main.detect_lang('Bonjour le monde'); -- fr\n"
                    "```\n\n"
                    "### Notes\n\n"
                    "- Empty/whitespace input returns `und` (undetermined).\n"
                    "- `NULL` input yields `NULL`.\n"
                    "- Most reliable on longer text; short strings can be ambiguous."
                ),
                keywords=[
                    "detect language",
                    "language detection",
                    "language identification",
                    "ISO 639-1",
                    "langid",
                    "what language",
                    "lang code",
                    "locale",
                    "nlp",
                ],
            ),
        }

    @classmethod
    def compute(
        cls,
        text: Annotated[pa.StringArray, Param(doc="Text whose language to detect.")],
    ) -> Annotated[pa.StringArray, Returns()]:
        """Map each input row to its output value."""
        out = [None if v is None else detect_language(v) for v in text.to_pylist()]
        return pa.array(out, type=pa.string())


SCALAR_FUNCTIONS: list[type] = [TranslateAuto, Translate, DetectLang]

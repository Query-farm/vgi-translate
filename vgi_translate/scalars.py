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

from typing import Annotated

import pyarrow as pa
from vgi.arguments import ConstParam, Param, Returns
from vgi.metadata import FunctionExample
from vgi.scalar_function import ScalarFunction

from .backend import detect_language, get_backend


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
        name = "translate"
        description = "Translate text into a target language (source auto-detected) using a local neural model"
        categories = ["translation", "nlp"]
        examples = [
            FunctionExample(
                sql="SELECT translate('Hello, world.', 'es')",
                description="Translate to Spanish, detecting the source language",
            ),
        ]

    @classmethod
    def compute(
        cls,
        text: Annotated[pa.StringArray, Param(doc="Text to translate.")],
        to_lang: Annotated[str, ConstParam("Target language code, e.g. 'es' (ISO 639-1).")],
    ) -> Annotated[pa.StringArray, Returns()]:
        return _translate_column(text, to_code=to_lang, from_code="auto")


class Translate(ScalarFunction):
    """``translate(text, to_lang, from_lang)`` — translate with an explicit source.

    Pass ``from_lang := 'auto'`` (or use the 2-arg overload) to detect the
    source language per row. Uses the configured backend (Argos Translate by
    default).
    """

    class Meta:
        name = "translate"
        description = "Translate text from an explicit source language into a target language (local neural model)"
        categories = ["translation", "nlp"]
        examples = [
            FunctionExample(
                sql="SELECT translate(comment, 'en', 'es') FROM reviews",
                description="Translate a Spanish column to English",
            ),
        ]

    @classmethod
    def compute(
        cls,
        text: Annotated[pa.StringArray, Param(doc="Text to translate.")],
        to_lang: Annotated[str, ConstParam("Target language code, e.g. 'es' (ISO 639-1).")],
        from_lang: Annotated[str, ConstParam("Source language code, or 'auto' to detect.")],
    ) -> Annotated[pa.StringArray, Returns()]:
        return _translate_column(text, to_code=to_lang, from_code=from_lang)


class DetectLang(ScalarFunction):
    """Detect the ISO 639-1 language code of each input string.

    Empty / whitespace-only input yields ``'und'`` (undetermined). Detection is
    fully offline (a bundled identification model), so it never downloads.
    """

    class Meta:
        name = "detect_lang"
        description = "Detect the ISO 639-1 language code of text"
        categories = ["translation", "nlp"]
        examples = [
            FunctionExample(
                sql="SELECT detect_lang('Bonjour le monde')",
                description="Returns 'fr'",
            ),
            FunctionExample(
                sql="SELECT detect_lang(body) FROM messages",
                description="Tag each message with its detected language",
            ),
        ]

    @classmethod
    def compute(
        cls,
        text: Annotated[pa.StringArray, Param(doc="Text whose language to detect.")],
    ) -> Annotated[pa.StringArray, Returns()]:
        out = [None if v is None else detect_language(v) for v in text.to_pylist()]
        return pa.array(out, type=pa.string())


SCALAR_FUNCTIONS: list[type] = [TranslateAuto, Translate, DetectLang]

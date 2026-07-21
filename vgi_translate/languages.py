"""A browsable reference view of common ISO 639-1 language codes.

Translation and detection both key on ISO 639-1 two-letter codes, but nothing in
the function surface tells an analyst *which* codes to pass. This module exposes a
small, static ``languages`` view (code + English name) so the valid inputs are
discoverable by a plain ``SELECT`` — no arguments to guess — which is exactly the
"browsable entry point" an agent needs before it can call ``translate``.

The list is a curated, representative set of languages the default Argos / OPUS-MT
backend commonly supports. It is intentionally not exhaustive and makes no promise
that every pair is installable: availability of a specific ``source -> target``
package is resolved lazily at translate time (see :mod:`vgi_translate.backend`).
"""

from __future__ import annotations

from vgi.catalog import View

from .meta import object_tags

# (ISO 639-1 code, English name), ordered by English name. Curated to the
# languages the default Argos/OPUS-MT backend commonly ships packages for.
_LANGUAGES: list[tuple[str, str]] = [
    ("sq", "Albanian"),
    ("ar", "Arabic"),
    ("az", "Azerbaijani"),
    ("bn", "Bengali"),
    ("bg", "Bulgarian"),
    ("ca", "Catalan"),
    ("zh", "Chinese"),
    ("cs", "Czech"),
    ("da", "Danish"),
    ("nl", "Dutch"),
    ("en", "English"),
    ("eo", "Esperanto"),
    ("et", "Estonian"),
    ("fi", "Finnish"),
    ("fr", "French"),
    ("de", "German"),
    ("el", "Greek"),
    ("he", "Hebrew"),
    ("hi", "Hindi"),
    ("hu", "Hungarian"),
    ("id", "Indonesian"),
    ("ga", "Irish"),
    ("it", "Italian"),
    ("ja", "Japanese"),
    ("ko", "Korean"),
    ("lv", "Latvian"),
    ("lt", "Lithuanian"),
    ("ms", "Malay"),
    ("nb", "Norwegian"),
    ("fa", "Persian"),
    ("pl", "Polish"),
    ("pt", "Portuguese"),
    ("ro", "Romanian"),
    ("ru", "Russian"),
    ("sk", "Slovak"),
    ("sl", "Slovenian"),
    ("es", "Spanish"),
    ("sv", "Swedish"),
    ("tl", "Tagalog"),
    ("th", "Thai"),
    ("tr", "Turkish"),
    ("uk", "Ukrainian"),
    ("ur", "Urdu"),
    ("vi", "Vietnamese"),
]


def _values_clause() -> str:
    """Render the language list as a DuckDB ``VALUES`` row set."""
    rows = ", ".join(f"('{code}', '{name}')" for code, name in _LANGUAGES)
    return f"SELECT code, name FROM (VALUES {rows}) AS t(code, name) ORDER BY name"


_LANGUAGES_EXAMPLE_QUERIES = (
    '[{"description": "Look up the ISO 639-1 code for a language by its English name.", '
    '"sql": "SELECT code FROM translate.main.languages WHERE name = \'Spanish\'"}, '
    '{"description": "Count how many reference languages are listed.", '
    '"sql": "SELECT count(*) AS n FROM translate.main.languages"}]'
)


LANGUAGES_VIEW = View(
    name="languages",
    definition=_values_clause(),
    comment="Common ISO 639-1 language codes (and English names) accepted by translate and detect_lang.",
    column_comments={
        "code": "ISO 639-1 two-letter language code to pass as the source/target of translate() or translate_all().",
        "name": "English name of the language.",
    },
    tags={
        **object_tags(
            title="Supported Language Codes",
            doc_llm=(
                "# languages\n\n"
                "A browsable reference of common **ISO 639-1** language codes and their "
                "English names, so you can discover the valid `source` / `target` values "
                "for `translate`, `translate_all`, and the codes `detect_lang` returns "
                "without guessing.\n\n"
                "**Columns**\n"
                "- `code` (`VARCHAR`): the two-letter ISO 639-1 code, e.g. `'es'`, `'fr'`, "
                "`'de'`.\n"
                "- `name` (`VARCHAR`): the English name of the language.\n\n"
                "**When to use**: browse it to find a code, or join it to a `detect_lang` "
                "result to label detected rows with a human-readable language name.\n\n"
                "**Note**: this is a curated, representative list of languages the default "
                "Argos / OPUS-MT backend commonly supports — not an exhaustive catalog, and "
                "not a guarantee that every `source -> target` pair has an installable "
                "package (that is resolved lazily at translate time)."
            ),
            doc_md=(
                "## languages\n\n"
                "A static reference of common **ISO 639-1** language codes and their English "
                "names. Use it to discover which codes to pass to `translate` / "
                "`translate_all`, or to join against a `detect_lang` result for a friendly "
                "label.\n\n"
                "### Notes\n\n"
                "- `code` is the two-letter ISO 639-1 code (e.g. `es`, `fr`, `de`).\n"
                "- The list is representative, not exhaustive; package availability for a "
                "specific pair is resolved at translate time."
            ),
            keywords=[
                "languages",
                "language codes",
                "ISO 639-1",
                "supported languages",
                "language list",
                "locale codes",
                "reference",
            ],
        ),
        "vgi.category": "reference",
        # VGI123 classifying facets use BARE keys (not vgi.-namespaced), matching
        # the schema's own domain/category/topic tags.
        "domain": "natural-language-processing",
        "topic": "reference-data",
        "vgi.example_queries": _LANGUAGES_EXAMPLE_QUERIES,
    },
)

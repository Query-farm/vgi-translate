"""Composed example queries that combine several of this worker's objects.

Each SQL string is defined once here and referenced from every place that
publishes it: the schema-level ``vgi.example_queries`` list (``worker.py``) and
the example list of the object that drives the query (``scalars.py`` /
``tables.py``), where it sits within that object's first five examples so the
``vgi-lint`` agent simulator shows it. Descriptions match the rows each query
actually returns with the default Argos backend.
"""

from __future__ import annotations

# detect_lang -> languages: label each detected code with its English name.
# Offline and deterministic (py3langid + a static view), so it is also published
# as an executable example on detect_lang.
DETECT_AND_NAME_SQL = (
    "WITH detected AS ("
    "SELECT id, body, translate.main.detect_lang(body) AS code "
    "FROM (VALUES (1, 'Bonjour le monde, comment allez-vous ce matin?'), "
    "(2, 'Guten Morgen, wie geht es Ihnen heute?'), "
    "(3, 'Hola, mucho gusto en conocerte.'), "
    "(4, 'The weather is lovely today.')) AS messages(id, body)) "
    "SELECT d.id, d.code, l.name AS language "
    "FROM detected AS d LEFT JOIN translate.main.languages AS l ON l.code = d.code "
    "ORDER BY d.id"
)
DETECT_AND_NAME = {
    "description": (
        "Detect the language of each message and label it with its English name from the "
        "languages reference view (returns fr/French, de/German, es/Spanish, en/English)."
    ),
    "sql": DETECT_AND_NAME_SQL,
}

# detect_lang filter -> translate (explicit source): translate only the Spanish rows.
TRANSLATE_DETECTED_SPANISH_SQL = (
    "SELECT id, body, translate.main.translate(body, 'en', 'es') AS english "
    "FROM (VALUES (1, 'El envío llegó tarde y la caja estaba dañada.'), "
    "(2, 'Great product, works as described.'), "
    "(3, 'Muy buena calidad, lo recomiendo.')) AS reviews(id, body) "
    "WHERE translate.main.detect_lang(body) = 'es' "
    "ORDER BY id"
)
TRANSLATE_DETECTED_SPANISH = {
    "description": (
        "Use detect_lang to pick out the Spanish rows of a mixed-language review table and "
        "translate only those into English with an explicit 'es' source (the English review "
        "is filtered out; reviews 1 and 3 come back translated)."
    ),
    "sql": TRANSLATE_DETECTED_SPANISH_SQL,
}

# translate_all (auto source) -> languages: normalize a mixed table to English and
# name each row's detected source language.
TRANSLATE_ALL_NAMED_SOURCE_SQL = (
    "SELECT t.id, l.name AS source_language, t.text, t.translation "
    "FROM translate.main.translate_all("
    "(SELECT id, body FROM (VALUES (1, 'El envío llegó tarde y la caja estaba dañada.'), "
    "(2, 'Great product, works as described.'), "
    "(3, 'Muy buena calidad, lo recomiendo.')) AS reviews(id, body)), "
    "id := 'id', target := 'en', source := 'auto') AS t "
    "LEFT JOIN translate.main.languages AS l ON l.code = t.src_lang "
    "ORDER BY t.id"
)
TRANSLATE_ALL_NAMED_SOURCE = {
    "description": (
        "Normalize a mixed Spanish/English review table to English in one batch, "
        "auto-detecting each row's source and naming it via the languages view "
        "(Spanish rows are translated; the English row passes through unchanged)."
    ),
    "sql": TRANSLATE_ALL_NAMED_SOURCE_SQL,
}

COMPOSED_EXAMPLES: list[dict[str, str]] = [
    DETECT_AND_NAME,
    TRANSLATE_DETECTED_SPANISH,
    TRANSLATE_ALL_NAMED_SOURCE,
]

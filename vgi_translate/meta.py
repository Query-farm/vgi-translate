"""Per-object discovery/description metadata helpers for the ``vgi-lint`` strict profile.

The strict profile expects these on **every** function and table. Each
function/table surfaces these in its ``Meta.tags``:

- ``vgi.title`` (VGI124)        — human-friendly display name (must not
  normalize-equal the machine name).
- ``vgi.doc_llm`` (VGI112)      — Markdown narrative aimed at an LLM/agent.
- ``vgi.doc_md`` (VGI113)       — Markdown narrative aimed at human docs
  (distinct content from ``doc_llm``).
- ``vgi.keywords`` (VGI126/VGI138) — search terms/synonyms, serialized as a
  **JSON array of strings** (not a comma-separated string).

``vgi.source_url`` is intentionally **not** emitted per object: VGI139 requires
it on the catalog only, so it lives once on the catalog ``source_url`` field.
"""

from __future__ import annotations

import json


def keywords_json(keywords: list[str]) -> str:
    """Serialize keywords as a JSON array of strings for ``vgi.keywords`` (VGI138)."""
    return json.dumps(keywords)


def object_tags(
    *,
    title: str,
    doc_llm: str,
    doc_md: str,
    keywords: list[str],
) -> dict[str, str]:
    """Build the standard per-object discovery/description tags.

    Args:
        title: Human-friendly display name for the object.
        doc_llm: Markdown narrative aimed at an LLM/agent.
        doc_md: Markdown narrative aimed at human documentation.
        keywords: Search terms/synonyms, emitted as a JSON array (VGI138).

    Returns:
        A mapping of ``vgi.*`` tag keys to their string values.
    """
    return {
        "vgi.title": title,
        "vgi.doc_llm": doc_llm,
        "vgi.doc_md": doc_md,
        "vgi.keywords": keywords_json(keywords),
    }

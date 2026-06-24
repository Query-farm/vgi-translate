"""Per-object discovery/description metadata helpers for the ``vgi-lint`` strict profile.

The 0.26.0 strict profile expects these on **every** function and table.
Each function/table surfaces these in its ``Meta.tags``:

- ``vgi.title`` (VGI124)        — human-friendly display name (must not
  normalize-equal the machine name).
- ``vgi.doc_llm`` (VGI112)      — Markdown narrative aimed at an LLM/agent.
- ``vgi.doc_md`` (VGI113)       — Markdown narrative aimed at human docs
  (distinct content from ``doc_llm``).
- ``vgi.keywords`` (VGI126)     — comma-separated search terms/synonyms.
- ``vgi.source_url`` (VGI128)   — link to the implementing source file.

``source_url(file)`` builds the canonical GitHub blob URL for a source file so
every object points at exactly where it is implemented.
"""

from __future__ import annotations

_SOURCE_BASE = "https://github.com/Query-farm/vgi-translate/blob/main/vgi_translate"


def source_url(relative_path: str) -> str:
    """Build the ``vgi.source_url`` for a file under ``vgi_translate/``."""
    return f"{_SOURCE_BASE}/{relative_path}"


def object_tags(
    *,
    title: str,
    doc_llm: str,
    doc_md: str,
    keywords: str,
    relative_path: str,
) -> dict[str, str]:
    """Build the five standard per-object discovery/description tags."""
    return {
        "vgi.title": title,
        "vgi.doc_llm": doc_llm,
        "vgi.doc_md": doc_md,
        "vgi.keywords": keywords,
        "vgi.source_url": source_url(relative_path),
    }

"""Translation + language-detection backends with per-process caching.

This is the per-process state VGI's pooled, persistent worker exists for: the
translation packages and the language-identification model are loaded once on
first use and cached for the lifetime of the worker process, so subsequent
calls (and every row of a batch) reuse them.

Backends
--------
* ``argos`` (default, **MIT**): :class:`ArgosBackend`. Uses Argos Translate,
  which downloads permissively-licensed OPUS-MT language-pair packages on
  demand from the Argos package index and caches them under the standard Argos
  data home (``~/.local/share/argos-translate`` or ``ARGOS_PACKAGES_DIR``).
  Language pairs are installed lazily on first use; if a pair cannot be
  installed (e.g. offline and not already cached), a clear error is raised.

The backend is selected by the ``VGI_TRANSLATE_BACKEND`` environment variable
(default ``argos``) so a deployer can swap in another backend — e.g. a
CTranslate2 backend with a model they license themselves — without touching the
function code. See the README's licensing section before choosing a non-default
model: NLLB-200 weights are CC-BY-NC (non-commercial) and must not be the
default for a commercial marketplace.
"""

from __future__ import annotations

import logging
import os
import threading
from abc import ABC, abstractmethod
from functools import lru_cache

log = logging.getLogger(__name__)

# Source-language sentinel: callers pass from := 'auto' to request detection.
AUTO = "auto"


class TranslationError(RuntimeError):
    """A translation or model-loading failure surfaced to SQL with a clear message."""


def normalize_lang(code: str) -> str:
    """Normalize a user-supplied language code (lowercase, strip region suffix).

    ``"EN"`` -> ``"en"``; ``"pt-BR"`` -> ``"pt"``. Argos packages key on the
    ISO 639-1 language code, not the regional variant.
    """
    code = (code or "").strip().lower()
    if not code:
        return code
    # Split on the first region/script separator (e.g. en-US, zh_Hans).
    for sep in ("-", "_"):
        if sep in code:
            code = code.split(sep, 1)[0]
            break
    return code


# ---------------------------------------------------------------------------
# Language detection (py3langid: BSD-licensed, ships its model, fully offline)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _langid_identifier():
    """Build and cache the py3langid identifier once per process."""
    try:
        from py3langid.langid import MODEL_FILE, LanguageIdentifier
    except Exception as exc:  # pragma: no cover - import guarded for clarity
        raise TranslationError(
            "language detection requires the 'py3langid' package; install it or "
            "pass an explicit source language (e.g. from := 'en')"
        ) from exc
    return LanguageIdentifier.from_pickled_model(MODEL_FILE, norm_probs=True)


def detect_language(text: str) -> str:
    """Return the ISO 639-1 code of ``text``'s language (e.g. ``"en"``).

    Empty / whitespace-only input returns ``"und"`` (undetermined).
    """
    if text is None or not text.strip():
        return "und"
    lang, _prob = _langid_identifier().classify(text)
    return str(lang)


# ---------------------------------------------------------------------------
# Translation backends
# ---------------------------------------------------------------------------


class Backend(ABC):
    """A translation backend: resolves source language and translates strings."""

    @abstractmethod
    def translate(self, text: str, *, to_code: str, from_code: str) -> str:
        """Translate ``text`` into ``to_code``.

        ``from_code`` may be :data:`AUTO`, in which case the backend detects the
        source language per string. Returns the translated text; passes through
        empty input unchanged.
        """

    def resolve_source(self, text: str, from_code: str) -> str:
        """Resolve ``from_code`` to a concrete language, detecting when ``auto``."""
        from_code = normalize_lang(from_code) or AUTO
        if from_code == AUTO:
            return detect_language(text)
        return from_code


def _argos_pair_available(from_code: str, to_code: str) -> bool:
    """True if Argos already has an installed translation for the pair.

    ``get_translation_from_codes`` raises (rather than returning None) when the
    pair is missing, so this wraps it in a boolean check.
    """
    import argostranslate.translate as translate

    try:
        return translate.get_translation_from_codes(from_code, to_code) is not None
    except Exception:
        return False


class ArgosBackend(Backend):
    """Argos Translate backend (MIT). Lazily installs + caches OPUS-MT packages."""

    def __init__(self) -> None:
        # Guards lazy package installation: argostranslate's package index and
        # install are not safe to run concurrently, and a pooled worker may see
        # overlapping calls.
        self._lock = threading.Lock()
        self._installed: set[tuple[str, str]] = set()
        self._index_updated = False

    def _ensure_pair(self, from_code: str, to_code: str) -> None:
        """Ensure the ``from_code -> to_code`` package is installed (idempotent)."""
        import argostranslate.package as pkg

        key = (from_code, to_code)
        if key in self._installed:
            return

        with self._lock:
            if key in self._installed:
                return

            # Already installed in a previous process / run?
            if _argos_pair_available(from_code, to_code):
                self._installed.add(key)
                return

            try:
                if not self._index_updated:
                    pkg.update_package_index()
                    self._index_updated = True
                installed = pkg.install_package_for_language_pair(from_code, to_code)
            except Exception as exc:
                raise TranslationError(
                    f"could not install the Argos '{from_code}->{to_code}' language "
                    f"package (offline or unavailable?): {exc}. Pre-install it with "
                    f"`argospm install translate-{from_code}_{to_code}` or run once with "
                    f"network access; the package is then cached for future calls."
                ) from exc

            # install_package_for_language_pair returns False when nothing was
            # installed; treat a still-missing translation as a hard error.
            if not _argos_pair_available(from_code, to_code):
                raise TranslationError(
                    f"no Argos translation available for '{from_code}->{to_code}'. "
                    f"Argos may not publish this pair directly (it can sometimes pivot "
                    f"through English — translate to/from 'en' in two steps), or the "
                    f"language codes are wrong."
                )
            _ = installed
            self._installed.add(key)

    def translate(self, text: str, *, to_code: str, from_code: str) -> str:
        import argostranslate.translate as translate

        if text is None:
            return text
        to_code = normalize_lang(to_code)
        if not to_code:
            raise TranslationError("target language ('to') is required, e.g. to := 'es'")
        src = self.resolve_source(text, from_code)
        # Nothing to do when source == target, or for empty / undetectable input.
        if not text.strip() or src in ("und", to_code):
            return text
        self._ensure_pair(src, to_code)
        try:
            return translate.translate(text, src, to_code)
        except Exception as exc:
            raise TranslationError(f"translation '{src}->{to_code}' failed: {exc}") from exc


_BACKENDS: dict[str, type[Backend]] = {
    "argos": ArgosBackend,
}


@lru_cache(maxsize=1)
def get_backend() -> Backend:
    """Return the process-wide translation backend, constructed once and cached.

    Selected by the ``VGI_TRANSLATE_BACKEND`` env var (default ``argos``). The
    instance owns the lazily-loaded, cached translation packages, so the whole
    point of VGI's persistent worker — load the model once, reuse it for every
    call — is realized here.
    """
    name = os.environ.get("VGI_TRANSLATE_BACKEND", "argos").strip().lower()
    backend_cls = _BACKENDS.get(name)
    if backend_cls is None:
        raise TranslationError(
            f"unknown backend {name!r}; available: {', '.join(sorted(_BACKENDS))}. "
            f"Set VGI_TRANSLATE_BACKEND to one of these."
        )
    return backend_cls()

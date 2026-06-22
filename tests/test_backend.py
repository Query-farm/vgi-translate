"""Unit tests for the translation backend helpers (offline, no downloads)."""

from __future__ import annotations

import pytest

from vgi_translate.backend import (
    TranslationError,
    detect_language,
    get_backend,
    normalize_lang,
)


class TestNormalizeLang:
    def test_lowercases(self) -> None:
        assert normalize_lang("EN") == "en"

    def test_strips_region(self) -> None:
        assert normalize_lang("pt-BR") == "pt"
        assert normalize_lang("zh_Hans") == "zh"

    def test_blank(self) -> None:
        assert normalize_lang("") == ""
        assert normalize_lang("  ") == ""

    def test_whitespace_around_code(self) -> None:
        assert normalize_lang("  En  ") == "en"


class TestDetectLanguage:
    def test_english(self) -> None:
        assert detect_language("Hello, how are you doing today?") == "en"

    def test_spanish(self) -> None:
        assert detect_language("Hola, ¿cómo estás hoy? Espero que todo vaya muy bien.") == "es"

    def test_french(self) -> None:
        assert detect_language("Bonjour, comment allez-vous aujourd'hui mon ami?") == "fr"

    def test_empty_is_undetermined(self) -> None:
        assert detect_language("") == "und"
        assert detect_language("   ") == "und"

    def test_tabs_and_newlines_are_undetermined(self) -> None:
        assert detect_language("\t\n  \r") == "und"

    def test_very_long_text(self) -> None:
        # A long, unambiguously English paragraph still detects as English and
        # does not raise.
        text = ("The quick brown fox jumps over the lazy dog. " * 200).strip()
        assert detect_language(text) == "en"

    def test_mixed_language_returns_a_single_code(self) -> None:
        # py3langid returns one dominant code for mixed input; we don't pin
        # which, only that it's a non-empty 2-letter-ish code (not 'und').
        result = detect_language("Hello world. Bonjour le monde. Hola mundo.")
        assert result and result != "und" and result.isalpha()


class TestBackendSelection:
    def test_default_is_argos(self) -> None:
        backend = get_backend()
        assert type(backend).__name__ == "ArgosBackend"

    def test_unknown_backend_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        get_backend.cache_clear()
        monkeypatch.setenv("VGI_TRANSLATE_BACKEND", "does-not-exist")
        with pytest.raises(TranslationError, match="unknown backend"):
            get_backend()
        get_backend.cache_clear()


class TestResolveSource:
    def test_explicit_passthrough(self) -> None:
        backend = get_backend()
        assert backend.resolve_source("anything", "fr") == "fr"

    def test_auto_detects(self) -> None:
        backend = get_backend()
        assert backend.resolve_source("Hello there, friend.", "auto") == "en"

    def test_blank_defaults_to_auto(self) -> None:
        backend = get_backend()
        assert backend.resolve_source("Bonjour le monde", "") == "fr"


class TestTranslateEdgeCasesOffline:
    """Edge cases that short-circuit before any model download is needed."""

    def test_empty_string_passes_through(self) -> None:
        backend = get_backend()
        assert backend.translate("", to_code="es", from_code="en") == ""

    def test_whitespace_only_passes_through(self) -> None:
        backend = get_backend()
        assert backend.translate("   \t\n", to_code="es", from_code="en") == "   \t\n"

    def test_none_passes_through(self) -> None:
        backend = get_backend()
        # NULL/None is preserved (the scalar/table layers skip None, but the
        # backend is defensive too).
        assert backend.translate(None, to_code="es", from_code="en") is None  # type: ignore[arg-type]

    def test_source_equals_target_is_noop(self) -> None:
        backend = get_backend()
        assert backend.translate("Hello, world.", to_code="en", from_code="en") == "Hello, world."

    def test_undetectable_source_passes_through(self) -> None:
        backend = get_backend()
        # Whitespace-only -> source detected as 'und' -> nothing translated.
        assert backend.translate("   ", to_code="es", from_code="auto") == "   "

    def test_missing_target_errors(self) -> None:
        backend = get_backend()
        with pytest.raises(TranslationError, match="target language"):
            backend.translate("Hello, world.", to_code="", from_code="en")


@pytest.mark.download
class TestTranslateUnknownLanguages:
    """Unknown language codes raise a clear ``TranslationError`` (needs the
    Argos package index, hence ``download``-marked / network on first run)."""

    def test_unknown_target_language(self) -> None:
        backend = get_backend()
        with pytest.raises(TranslationError, match="no Argos translation available|could not install"):
            backend.translate("Hello, world.", to_code="zz", from_code="en")

    def test_unknown_source_language(self) -> None:
        backend = get_backend()
        with pytest.raises(TranslationError, match="no Argos translation available|could not install"):
            backend.translate("Hello, world.", to_code="es", from_code="zz")

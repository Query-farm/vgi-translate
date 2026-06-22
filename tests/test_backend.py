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

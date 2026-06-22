"""Integration tests driving the worker through ``vgi.client.Client``.

These spawn the real worker subprocess (``translate_worker.py``) and exercise it
over the VGI protocol, mirroring how DuckDB calls it.

``detect_lang`` runs fully offline (bundled identification model). The real
``translate`` / ``translate_all`` tests need the Argos ``en->es`` package; they
are marked ``download`` and self-skip when the package can't be installed (e.g.
no network and not already cached), so the suite stays green offline.
"""

from __future__ import annotations

import pathlib

import pyarrow as pa
import pytest
from vgi import Arguments
from vgi.client import Client

WORKER = str(pathlib.Path(__file__).resolve().parent.parent / "translate_worker.py")


def _client() -> Client:
    # server_path is a shell command. Use the current interpreter so the worker
    # runs in the same (already-installed) environment as the tests, rather than
    # re-resolving deps via `uv run`. worker_limit=1 keeps output order aligned
    # with input order so per-row assertions are deterministic.
    import sys

    return Client(f"{sys.executable} {WORKER}", worker_limit=1)


def _en_es_installable() -> bool:
    """True if the Argos en->es package is installed or can be installed now."""
    try:
        import argostranslate.package as pkg

        from vgi_translate.backend import _argos_pair_available

        if _argos_pair_available("en", "es"):
            return True
        pkg.update_package_index()
        return pkg.install_package_for_language_pair("en", "es") or _argos_pair_available("en", "es")
    except Exception:
        return False


def _detect(client: Client, texts: list[str | None]) -> list[str | None]:
    batch = pa.RecordBatch.from_pydict({"text": texts})
    results = list(
        client.scalar_function(
            function_name="detect_lang",
            input=iter([batch]),
            arguments=Arguments(positional=[pa.scalar("text")]),
        )
    )
    return results[0]["result"].to_pylist()


class TestDetectLang:
    def test_detects_languages(self) -> None:
        with _client() as client:
            assert _detect(
                client,
                [
                    "Hello, how are you doing today my friend?",
                    "Hola, ¿cómo estás hoy? Espero que todo vaya muy bien.",
                    "Bonjour, comment allez-vous aujourd'hui mon ami?",
                ],
            ) == ["en", "es", "fr"]

    def test_empty_whitespace_and_null(self) -> None:
        # Empty / whitespace-only -> 'und'; NULL passes through as None.
        with _client() as client:
            assert _detect(client, ["", "   ", "\t\n", None]) == ["und", "und", "und", None]

    def test_very_long_text(self) -> None:
        long_text = ("The quick brown fox jumps over the lazy dog. " * 200).strip()
        with _client() as client:
            assert _detect(client, [long_text]) == ["en"]


@pytest.mark.download
class TestTranslateScalar:
    def test_translate_en_to_es(self) -> None:
        if not _en_es_installable():
            pytest.skip("Argos en->es package unavailable (offline and not cached)")

        batch = pa.RecordBatch.from_pydict({"text": ["Hello, world."]})
        with _client() as client:
            results = list(
                client.scalar_function(
                    function_name="translate",
                    input=iter([batch]),
                    # The `text` column is supplied by the input batch (a Param);
                    # only the constant args go in `positional`: to_lang, from_lang.
                    arguments=Arguments(positional=[pa.scalar("es"), pa.scalar("en")]),
                )
            )
        out = results[0]["result"].to_pylist()[0]
        assert out and out != "Hello, world."
        assert "hola" in out.lower() or "mundo" in out.lower()

    def test_translate_auto_detect_source(self) -> None:
        if not _en_es_installable():
            pytest.skip("Argos en->es package unavailable (offline and not cached)")

        # A clearly-English sentence so detection is unambiguous (py3langid is
        # unreliable on very short strings like "Hello, world.").
        batch = pa.RecordBatch.from_pydict({"text": ["The weather is nice today and I am going for a walk."]})
        with _client() as client:
            results = list(
                client.scalar_function(
                    function_name="translate",
                    input=iter([batch]),
                    # Only to_lang given -> from_lang defaults to 'auto' (detected as 'en').
                    arguments=Arguments(positional=[pa.scalar("es")]),
                )
            )
        out = results[0]["result"].to_pylist()[0]
        assert out and out != "The weather is nice today and I am going for a walk."


def _translate(client: Client, texts: list[str | None], *, positional: list[object]) -> list[str | None]:
    batch = pa.RecordBatch.from_pydict({"text": texts})
    results = list(
        client.scalar_function(
            function_name="translate",
            input=iter([batch]),
            arguments=Arguments(positional=[pa.scalar(p) for p in positional]),
        )
    )
    return results[0]["result"].to_pylist()


class TestTranslateScalarEdgeCases:
    """Edge cases that short-circuit before any model download (run offline)."""

    def test_empty_whitespace_and_null_pass_through(self) -> None:
        # Empty / whitespace pass through unchanged; NULL stays NULL. No package
        # download is triggered, so this runs without the `download` marker.
        with _client() as client:
            assert _translate(client, ["", "   ", None], positional=["es", "en"]) == ["", "   ", None]

    def test_source_equals_target_is_noop(self) -> None:
        with _client() as client:
            assert _translate(client, ["Hello, world."], positional=["en", "en"]) == ["Hello, world."]


@pytest.mark.download
class TestTranslateScalarErrors:
    def test_unknown_target_language_errors(self) -> None:
        # An unknown target code surfaces a clear worker error (needs the Argos
        # package index to confirm the pair is unavailable).
        import pytest as _pytest

        with _client() as client:
            with _pytest.raises(Exception, match="no Argos translation available|could not install"):
                _translate(client, ["Hello, world."], positional=["zz", "en"])


@pytest.mark.download
class TestTranslateAll:
    def test_table_in_out_with_id_passthrough(self) -> None:
        if not _en_es_installable():
            pytest.skip("Argos en->es package unavailable (offline and not cached)")

        batch = pa.RecordBatch.from_pydict({"id": [1, 2], "body": ["Hello, world.", "Good morning."]})
        with _client() as client:
            results = list(
                client.table_in_out_function(
                    function_name="translate_all",
                    input=iter([batch]),
                    # The table input is the streamed `input`; only named args
                    # go in `arguments`.
                    arguments=Arguments(
                        named={"id": pa.scalar("id"), "target": pa.scalar("es"), "source": pa.scalar("en")},
                    ),
                )
            )
        table = pa.Table.from_batches(results)
        assert table.column_names == ["id", "text", "translation", "src_lang"]
        assert table.column("id").to_pylist() == [1, 2]
        assert table.column("src_lang").to_pylist() == ["en", "en"]
        translations = table.column("translation").to_pylist()
        assert all(t for t in translations)
        assert translations != ["Hello, world.", "Good morning."]

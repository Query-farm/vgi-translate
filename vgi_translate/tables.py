"""Batched table-in-out translation: ``translate_all``.

``translate_all`` streams a table of ``(id, text)`` rows through the translation
backend and emits ``(id, text, translation, src_lang)``. It is the throughput
path: it batches whole record batches and reuses the per-process model cache, so
a single Argos package load serves the entire scan.

    SELECT * FROM translate.translate_all(
        (SELECT id, body FROM messages),
        id := 'id', target := 'es', source := 'auto');

Column roles
------------
* ``id``  -- a passthrough column, excluded from translation and copied
  unchanged onto each output row so you can join the result back to the source.
* the remaining (single) text column is translated.

Named arguments (``id :=``, ``target :=``, ``source :=``) use DuckDB's
``name := value`` syntax, which table functions support. (``target`` / ``source``
rather than ``to`` / ``from`` because the latter are SQL reserved keywords.)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, ClassVar

import pyarrow as pa
from vgi.arguments import Arg, TableInput
from vgi.invocation import BindResponse
from vgi.metadata import FunctionExample
from vgi.table_function import BindParams, ProcessParams
from vgi.table_in_out_function import TableInOutGenerator
from vgi_rpc.rpc import OutputCollector

from .backend import AUTO, get_backend, normalize_lang
from .schema_utils import field


@dataclass(slots=True, frozen=True)
class TranslateAllArgs:
    """Arguments for the ``translate_all`` table-in-out function."""

    # NOTE on argument names: DuckDB exposes each named argument under its
    # *field name* and looks the supplied value up by the same name, so the
    # field name and the ``Arg(...)`` alias MUST match. ``to`` / ``from`` would
    # be ideal but are SQL reserved keywords (and ``from`` is a Python keyword,
    # so it can only be the field ``from_`` — a name DuckDB then can't route a
    # value to). We therefore use the non-reserved ``target`` / ``source``.
    data: Annotated[TableInput, Arg(0, doc="Table to translate (an id column + one text column).")]
    target: Annotated[str, Arg("target", default="", doc="Target language code, e.g. 'es' (ISO 639-1). Required.")]
    source: Annotated[
        str,
        Arg("source", default=AUTO, doc="Source language code, or 'auto' to detect per row (default 'auto')."),
    ]
    id: Annotated[str, Arg("id", default="", doc="Name of an id column to carry through (excluded from translation).")]


def _text_column(input_schema: pa.Schema, id_col: str) -> str:
    """Return the single text column: the one input column that is not the id."""
    candidates: list[str] = [n for n in input_schema.names if n != id_col]
    if not candidates:
        raise ValueError(
            f"translate_all needs a text column to translate; the input only contains the id column {id_col!r}"
        )
    if len(candidates) > 1:
        raise ValueError(
            "translate_all translates exactly one text column; the input has "
            f"multiple non-id columns ({', '.join(candidates)}). SELECT just "
            f"the id column and the one text column."
        )
    return candidates[0]


class TranslateAll(TableInOutGenerator[TranslateAllArgs]):
    """Batched translation of a streamed table, with id passthrough."""

    FunctionArguments: ClassVar[type] = TranslateAllArgs

    class Meta:
        """Function metadata."""

        name = "translate_all"
        description = "Translate a table of text rows in batch, carrying an id column through"
        categories = ["translation", "nlp", "batch"]
        examples = [
            FunctionExample(
                sql=(
                    "SELECT * FROM translate.main.translate_all("
                    "(SELECT id, body FROM messages), id := 'id', target := 'es', source := 'auto')"
                ),
                description="Translate a messages table to Spanish in batch, detecting the source language per row",
            )
        ]
        tags = {
            "vgi.columns_md": (
                "| column | type | description |\n"
                "|---|---|---|\n"
                "| *id* | (input type) | The passthrough id column (present only when `id :=` is given), "
                "copied unchanged so the result joins back to the source. |\n"
                "| `text` | VARCHAR | The original source text. |\n"
                "| `translation` | VARCHAR | The translated text. |\n"
                "| `src_lang` | VARCHAR | Source language used (detected when `source := 'auto'`). |"
            ),
        }

    @classmethod
    def on_bind(cls, params: BindParams[TranslateAllArgs]) -> BindResponse:
        """Validate arguments and compute the output schema at plan time."""
        a = params.args
        input_schema = params.bind_call.input_schema
        assert input_schema is not None

        if not normalize_lang(a.target):
            raise ValueError("translate_all requires 'target' (the target language), e.g. target := 'es'")
        if a.id and a.id not in input_schema.names:
            raise ValueError(f"id column {a.id!r} not found in input; columns: {', '.join(input_schema.names)}")
        # Validate that exactly one text column is present (raises otherwise).
        _text_column(input_schema, a.id)

        fields: list[pa.Field] = []
        if a.id:
            fields.append(input_schema.field(a.id))
        fields.append(field("text", pa.string(), "The original source text.", nullable=True))
        fields.append(field("translation", pa.string(), "The translated text.", nullable=True))
        fields.append(
            field(
                "src_lang",
                pa.string(),
                "Source language used (detected when source := 'auto').",
                nullable=True,
            )
        )
        return BindResponse(output_schema=pa.schema(fields))

    @classmethod
    def process(
        cls,
        params: ProcessParams[TranslateAllArgs],
        state: None,
        batch: pa.RecordBatch,
        out: OutputCollector,
    ) -> None:
        """Translate each row of one input batch and emit the result batch."""
        a = params.args
        backend = get_backend()
        to_code = normalize_lang(a.target)

        text_col = _text_column(batch.schema, a.id)
        texts = batch.column(text_col).to_pylist()

        translations: list[str | None] = []
        src_langs: list[str | None] = []
        for value in texts:
            if value is None:
                translations.append(None)
                src_langs.append(None)
                continue
            src = backend.resolve_source(value, a.source)
            translations.append(backend.translate(value, to_code=to_code, from_code=src))
            src_langs.append(src)

        columns: dict[str, Any] = {}
        if a.id:
            columns[a.id] = batch.column(a.id).to_pylist()
        columns["text"] = texts
        columns["translation"] = translations
        columns["src_lang"] = src_langs
        out.emit(pa.RecordBatch.from_pydict(columns, schema=params.output_schema))


TABLE_FUNCTIONS: list[type] = [TranslateAll]

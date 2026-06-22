"""Batched table-in-out translation: ``translate_all``.

``translate_all`` streams a table of ``(id, text)`` rows through the translation
backend and emits ``(id, text, translation, src_lang)``. It is the throughput
path: it batches whole record batches and reuses the per-process model cache, so
a single Argos package load serves the entire scan.

    SELECT * FROM translate.translate_all(
        (SELECT id, body FROM messages),
        id := 'id', to := 'es', from := 'auto');

Column roles
------------
* ``id``  -- a passthrough column, excluded from translation and copied
  unchanged onto each output row so you can join the result back to the source.
* the remaining (single) text column is translated.

Named arguments (``id :=``, ``to :=``, ``from :=``) use DuckDB's ``name := value``
syntax, which table functions support.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, ClassVar

import pyarrow as pa
from vgi.arguments import Arg, TableInput
from vgi.invocation import BindResponse
from vgi.metadata import FunctionExample
from vgi.table_function import BindParams, ProcessParams
from vgi.table_in_out_function import OutputCollector, TableInOutGenerator

from .backend import AUTO, get_backend, normalize_lang
from .schema_utils import field


@dataclass(slots=True, frozen=True)
class TranslateAllArgs:
    data: Annotated[TableInput, Arg(0, doc="Table to translate (an id column + one text column).")]
    to: Annotated[str, Arg("to", default="", doc="Target language code, e.g. 'es' (ISO 639-1). Required.")]
    from_: Annotated[
        str,
        Arg("from", default=AUTO, doc="Source language code, or 'auto' to detect per row (default 'auto')."),
    ]
    id: Annotated[str, Arg("id", default="", doc="Name of an id column to carry through (excluded from translation).")]


def _text_column(input_schema: pa.Schema, id_col: str) -> str:
    """Return the single text column: the one input column that is not the id."""
    candidates = [n for n in input_schema.names if n != id_col]
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
        name = "translate_all"
        description = "Translate a table of text rows in batch, carrying an id column through"
        categories = ["translation", "nlp", "batch"]
        examples = [
            FunctionExample(
                sql=(
                    "SELECT * FROM translate.translate_all("
                    "(SELECT id, body FROM messages), id := 'id', to := 'es', from := 'auto')"
                ),
                description="Translate a messages table to Spanish, detecting the source language",
            )
        ]

    @classmethod
    def on_bind(cls, params: BindParams[TranslateAllArgs]) -> BindResponse:
        a = params.args
        input_schema = params.bind_call.input_schema
        assert input_schema is not None

        if not normalize_lang(a.to):
            raise ValueError("translate_all requires 'to' (the target language), e.g. to := 'es'")
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
                "Source language used (detected when from := 'auto').",
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
        a = params.args
        backend = get_backend()
        to_code = normalize_lang(a.to)

        text_col = _text_column(batch.schema, a.id)
        texts = batch.column(text_col).to_pylist()

        translations: list[str | None] = []
        src_langs: list[str | None] = []
        for value in texts:
            if value is None:
                translations.append(None)
                src_langs.append(None)
                continue
            src = backend.resolve_source(value, a.from_)
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

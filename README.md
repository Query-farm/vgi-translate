<p align="center">
  <img src="https://raw.githubusercontent.com/Query-farm/vgi/main/docs/vgi-logo.png" alt="Vector Gateway Interface (VGI)" width="320">
</p>

<p align="center"><em>A <a href="https://query.farm">Query.Farm</a> VGI worker for DuckDB.</em></p>

# vgi-translate

A [VGI](https://github.com/query-farm/vgi-python) worker that brings **local
neural machine translation** into DuckDB/SQL: translate columns of text and
detect languages, all as SQL functions, running on your own machine with no
external API calls.

```sql
INSTALL vgi FROM community; LOAD vgi;
ATTACH 'tr' (TYPE vgi, LOCATION 'uv run translate_worker.py');

SELECT tr.translate('Hello, world.', 'es');          -- 'Hola, mundo.'
SELECT tr.detect_lang('Bonjour le monde');           -- 'fr'
SELECT * FROM tr.translate_all(
  (SELECT id, body FROM messages), id := 'id', target := 'es', source := 'auto');
```

The first time you translate a given language pair, the worker downloads a small,
permissively-licensed model package for that pair and **caches it** for the
lifetime of the process and on disk. Translation then runs entirely locally.

## Licensing & models (read this first)

Machine-translation models carry very different licenses, and the wrong default
can make a commercial product non-compliant. This worker defaults to a model
ecosystem that is **safe for commercial use**:

| | Default here | A common alternative to avoid by default |
| --- | --- | --- |
| Backend | **Argos Translate** (`argostranslate`, **MIT**) | CTranslate2 + NLLB-200 |
| Models | OPUS-MT language packages (open, permissive) | **NLLB-200** weights |
| Model license | Permissive — usable commercially | **CC-BY-NC** — *non-commercial only* |

- **Default: Argos Translate (MIT).** Argos downloads OPUS-MT-derived
  language-pair packages on demand from its open package index. These are
  permissively licensed and suitable for a commercial marketplace. This is why
  it is the default.
- **NLLB-200 is deliberately *not* the default.** Meta's NLLB-200 models are
  excellent and cover 200 languages, but they are released under
  **CC-BY-NC 4.0 (non-commercial)**. Defaulting to them would push that
  non-commercial restriction onto every downstream user. Do not use them in a
  commercial product unless you have separately licensed them.
- **You can opt into other backends at your own licensing risk.** The backend is
  pluggable via the `VGI_TRANSLATE_BACKEND` environment variable (see
  [Backends & configuration](#backends--configuration)). If you bring your own
  CTranslate2 model (NLLB, M2M-100, a fine-tune, …), **you** are responsible for
  complying with that model's license.

Language **detection** uses [`py3langid`](https://github.com/adbar/py3langid)
(BSD-licensed), which ships its own identification model and runs fully offline —
no downloads, ever.

The worker code itself is under the
[Query Farm Source-Available License](LICENSE).

## How it maps translation onto SQL

| Task | SQL surface | VGI primitive |
| --- | --- | --- |
| **Translate one value/column** | `tr.translate(text, 'es')` | scalar function |
| **Detect a language** | `tr.detect_lang(text)` | scalar function |
| **Translate a whole table (batched)** | `tr.translate_all((SELECT id, text), id := 'id', target := 'es')` | table-in-out function |

**Conventions:**

- Models are loaded **once per worker process and cached** — the per-process
  state that VGI's pooled, persistent worker is built for. The first call for a
  language pair lazily installs its Argos package; subsequent calls (and every
  row of a batch) reuse the loaded model.
- Language codes are **ISO 639-1** (`en`, `es`, `fr`, `de`, …). Region/script
  suffixes are stripped (`pt-BR` → `pt`).
- `source := 'auto'` (the default) **detects the source language** per row.
- When the source already equals the target, or input is empty/undetectable, the
  text is returned **unchanged**.
- If a language pair can't be installed offline (and isn't cached), you get a
  **clear error** telling you how to pre-install it.

## Function catalog

### `translate(text, to_lang[, from_lang])` → VARCHAR  *(scalar)*

Translate each value of a text column into `to_lang`.

```sql
SELECT translate('Hello, world.', 'es');        -- source auto-detected → 'Hola, mundo.'
SELECT translate(body, 'en', 'es') FROM reviews; -- explicit source 'es' → English
```

> **Argument syntax.** DuckDB *scalar* functions take **positional** arguments
> and resolve overloads by arity — the `name := value` form is only for table
> functions and macros. So `translate` has two overloads: a 2-arg form
> (auto-detect the source) and a 3-arg form (explicit source). Use
> `translate(text, to, 'auto')` to force detection in the 3-arg form.

### `detect_lang(text)` → VARCHAR  *(scalar)*

Return the detected ISO 639-1 code of each string. Empty/whitespace-only input
returns `'und'` (undetermined). Runs fully offline.

```sql
SELECT detect_lang(body) AS lang, count(*) FROM messages GROUP BY lang;
```

### `translate_all((SELECT id, text), id := 'id', target := 'es', source := 'auto')` → `(id, text, translation, src_lang)`  *(table-in-out)*

Batched translation of a streamed table, with an **`id` passthrough column**.
This is the throughput path: it processes whole record batches and reuses the
per-process model cache, so a single model load serves the entire scan.

- `id` — a passthrough column: excluded from translation and copied unchanged
  onto each output row, so you can join the result back to the source. Optional.
- The single remaining (non-`id`) column is the text to translate.
- `target` — target language (required). `source` — source language or `'auto'`
  (default). (Named `target`/`source` rather than `to`/`from`, which are SQL
  reserved keywords.)
- Output columns: `id` (if given), `text` (original), `translation`, `src_lang`
  (the source language actually used; the detected code when `source := 'auto'`).

```sql
SELECT * FROM tr.translate_all(
  (SELECT id, body FROM messages), id := 'id', target := 'es', source := 'auto');

-- join translations back onto the source rows
SELECT m.*, t.translation, t.src_lang
FROM messages m
JOIN tr.translate_all((SELECT id, body FROM messages), id := 'id', target := 'en') t
  USING (id);
```

## Backends & configuration

| Env var | Default | Meaning |
| --- | --- | --- |
| `VGI_TRANSLATE_BACKEND` | `argos` | Translation backend to use. |
| `ARGOS_PACKAGES_DIR` | Argos default | Where Argos caches installed language packages. |

Only the `argos` backend ships today. The `Backend` abstraction in
`vgi_translate/backend.py` is the single seam where another backend (e.g. a
CTranslate2 + NLLB/M2M-100 backend you license yourself) drops in: implement
`translate(text, *, to_code, from_code)` and register it in `_BACKENDS`.

### Pre-installing language packages (for offline/air-gapped use)

Packages install automatically on first use when there's network access. To
pre-seed them so the worker never needs the network at query time:

```sh
argospm update
argospm install translate-en_es      # English ↔ Spanish, etc.
```

If a pair isn't available offline and isn't cached, `translate` returns a clear
error explaining how to install it. Note that Argos doesn't publish every direct
pair — some translations pivot through English (e.g. `de → es` as `de → en → es`),
which you can do in two steps if a direct package doesn't exist.

## Local development

```sh
uv sync                       # install vgi-python, argostranslate, py3langid
make test                     # unit (pytest) + end-to-end SQL (haybarn-unittest)
make test-unit                # full pytest suite (real en→es download test self-skips offline)
make test-offline             # offline-only: backend + detect_lang, no downloads
make test-sql                 # DuckDB sqllogictest E2E (installs the runner + en→es package)
uv run ruff check . && uv run ruff format --check .
```

**Unit tests** drive the **real worker subprocess** through `vgi.client.Client`,
exactly as DuckDB does. The heavy translation tests are marked `download`: they
install the Argos `en→es` package and **self-skip** when it can't be installed
(no network and not cached), so the suite stays green offline. `detect_lang`,
the backend unit tests, and the offline edge-case tests (empty/NULL/whitespace,
source==target, missing target) always run — they need no downloads.

**End-to-end SQL tests** (`test/sql/*.test`) run the worker under DuckDB through
the [`haybarn-unittest`](https://pypi.org/project/haybarn-unittest/)
sqllogictest runner (`uv tool install haybarn-unittest`). `make test-sql`
installs the runner and the Argos `en→es` package, then exercises `detect_lang`,
both `translate` overloads, `translate_all` (id passthrough + `src_lang`), and
clear-error cases for unknown language codes — against the actual SQL surface.
The `detect_lang` E2E case needs no download and always runs.

> Developing against a local `vgi-python` checkout? Uncomment `[tool.uv.sources]`
> in `pyproject.toml`, or `uv pip install -e ../vgi-python`.

## Layout

```
translate_worker.py      entry point; assembles the `translate` catalog, serves over stdio
vgi_translate/
  backend.py             pluggable backend (Argos default), detection, per-process model cache
  scalars.py             translate / detect_lang scalar functions
  tables.py              translate_all batched table-in-out (id passthrough)
  schema_utils.py        Arrow column-comment helper
tests/
  test_backend.py        offline unit tests (normalize, detect, backend selection, edge cases)
  test_translate.py      Client integration tests (detect_lang offline; translate gated on download)
test/sql/
  translate_detect.test  detect_lang E2E over a VALUES table (offline, always runs)
  translate_scalar.test  translate() E2E — both overloads, empty/NULL/no-op edges
  translate_all.test     translate_all E2E — id passthrough + (text, translation, src_lang)
  translate_errors.test  unknown / missing language codes -> clear SQL errors
scripts/
  ensure_argos_pair.py   idempotently installs an Argos language pair (used by `make test-sql`)
Makefile                 test / test-unit / test-offline / test-sql / lint
```

---

## Authorship & License

Written by [Query.Farm](https://query.farm).

Copyright 2026 Query Farm LLC - https://query.farm


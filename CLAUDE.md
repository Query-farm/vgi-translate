# CLAUDE.md — vgi-translate

Contributor/agent notes. User-facing docs live in `README.md`; this is the
"how it's built and where the sharp edges are" companion.

## What this is

A [VGI](https://query.farm) worker exposing **local neural machine translation**
to DuckDB/SQL via Argos Translate (MIT; OPUS-MT models). `translate_worker.py`
assembles every function into one `tr` catalog (single `main` schema) over
stdio. Runs fully local — no API keys.

## Layout

```
translate_worker.py    repo-root stdio entry; PEP 723 inline deps; main()
vgi_translate/
  backend.py           pluggable Backend ABC; Argos default; py3langid detection; per-process model/package cache
  scalars.py           translate (arity overloads) + detect_lang
  tables.py            translate_all (table-in-out, id passthrough)
  schema_utils.py      Arrow column-comment helper
scripts/ensure_argos_pair.py   installs/caches an Argos language pair (used by make test-sql)
tests/                 pytest: backend (offline) + translate (Client RPC, download-gated)
test/sql/*.test        haybarn-unittest sqllogictest — authoritative E2E
Makefile               test / test-unit / test-offline / ensure-haybarn / ensure-en-es / test-sql / lint
```

## Licensing — DO NOT regress this decision

- **Default backend is Argos Translate (MIT)** with OPUS-MT packages →
  commercial-safe. Packages install lazily on first use and cache per worker
  process (the per-process state VGI's persistent pool exists for).
- **NLLB-200 is CC-BY-NC (non-commercial) and is intentionally NOT the default.**
  The README has a prominent caveat. Backend is pluggable via
  `VGI_TRANSLATE_BACKEND` / the `Backend` ABC; bring-your-own models are the
  user's licensing risk. Keep the README licensing section accurate on changes.
- Language detection is `py3langid` (BSD), ships its model, fully offline.

## Scalars vs table functions — core convention (read first)

VGI **scalars are positional-only**. `translate` is therefore **arity
overloads**: `translate(text, target)` (auto-detect source) and `translate(text,
target, source)`. The **table** function `translate_all` uses named args.

## Sharp edges (learned the hard way)

1. **Named args route by dataclass FIELD NAME, not the `Arg()` alias.**
   `translate_all` originally used `to`/`from` aliases — DuckDB accepted `to :=`
   but the SDK dropped the value (source silently fell back to auto-detect), and
   `to`/`from` are SQL reserved words. The named args are now `target` / `source`
   (matching the field names). When adding a named table-fn arg, name the
   dataclass field exactly what the SQL caller will type.
2. **`haybarn-unittest` skips `require vgi`** — use explicit `LOAD vgi;` in
   `.test` files.
3. **Translation E2E needs the en→es Argos package.** `make test-sql` installs
   it via `scripts/ensure_argos_pair.py`. `detect_lang` E2E is offline and always
   runs; the real-translation tests are download-gated and self-skip if the
   package can't be fetched (pytest `-m "not download"` to force offline).
4. **Verified golden:** `tr.translate('Hello, world.', 'es')` → `Hola, mundo.`
   (both overloads + `translate_all`).

## Testing

```sh
uv run pytest -q              # full unit suite (download tests self-skip offline)
uv run pytest -m "not download"   # offline-only
make test-sql                 # E2E: installs en->es + haybarn-unittest over test/sql/*
make test                     # both
uv run ruff check .
```

`make test-sql` exports `VGI_TRANSLATE_WORKER="uv run --python 3.13
translate_worker.py"` and runs `haybarn-unittest --test-dir . "test/sql/*"`
(install once: `uv tool install haybarn-unittest`). **The SQL suite is
authoritative.** CI runs unit + an `e2e-sql` job (installs runner + en→es, runs
`make test-sql`); gateable if downloads flake, with `detect_lang` E2E always on.

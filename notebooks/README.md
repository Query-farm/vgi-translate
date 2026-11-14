# Translation notebooks

[01 · Translate or hold for review](01_translate_or_hold_for_review.ipynb) keeps every row in a synthetic message corpus while separating missing, blank, short, unsupported-language, already-English and Spanish-to-English paths. It uses the real worker for local language detection and neural translation, with explicit SQL routing, ID-preserving batches and exact text review.

## Run from this directory alone

Install [uv](https://docs.astral.sh/uv/) and Python 3.13 (worker) plus Python 3.13 or 3.14 for the notebook. First run downloads dependencies, the signed VGI extension, pinned Git worker, and one **285,208,831-byte** model package. Allow several minutes and roughly 1 GB for the model archive, extracted files and setup. Subsequent inference is local; no API key or worker checkout is required.

```sh
cd notebooks
uv sync --locked
uv run --locked python execute.py --timeout 360
uv run --locked python execute.py --timeout 360 --parameters '{"MIN_CHARS":5}' --output-dir validation/min-5
uv run --locked python -m ipykernel install --user --name vgi-translate-notebooks --display-name 'Python (vgi-translate notebooks)'
```

Use that kernel in Jupyter with this directory as cwd. Restart and Run All after editing. The runner creates a temporary kernel from its own environment, saves outputs atomically only on success, rejects unknown parameters, and requires separate output for overrides. Experiment copies include assets, model manifest/helper, README, standard, constraints, runner and lock. Logs, extracted charts, experiments and audit files are ignored; the main notebook retains embedded outputs.

The literal ATTACH uses `uvx --python 3.13 --from git+https://github.com/Query-farm/vgi-translate.git@332e36901e8292b58a0bc6794703b10dfac6dece --constraints worker-constraints.txt vgi-translate-worker`. This remotely available revision includes the float32 default fix added after v0.4.0; the older tag can produce bad Spanish→English int8 results on x86-64. No worker source or root lock is modified. Haybarn is pinned to 2.0.0rc11, with tested SDK 0.51.0/RPC 0.53.1, Argos 1.11.0, CTranslate2 4.8.5 and py3langid 0.4.0. Upgrade pins deliberately and revalidate both outputs and policy behavior.

## Model provenance and cache

`prepare_model.py` downloads exactly [Argos Spanish→English package 1.9](https://argos-net.com/v1/translate-es_en-1_9.argosmodel), SHA256 `c54df2b62fceaf54a3ce5d97db6bf56efd7940063329f6778f4212d2acb370d4`. `model-package.json` also records every extracted file hash and the package's original attribution. The Argos package bundles an older tokenizer index. Stanza 1.10.1 requires its current resource schema and normally refreshes that index and downloads Spanish tokenizer/multiword-token files during first inference. The notebook explicitly pins all three official Stanza 1.10.0 assets (1,732,430 additional bytes), with URLs and SHA256 hashes in the same manifest. Setup overlays those supported runtime resources in the private cache. Its resource URL/version points to an owned loopback server serving only the pinned index (at most four reads), with a request audit and rejection of other paths. No worker or library code is patched. All runtime asset hashes are checked both before and after inference. This is the actual model, not recorded translations or a synthetic fallback.

The helper uses a bounded installation lock, checks size/archive hash/member paths/member hashes, publishes atomically under `${XDG_CACHE_HOME:-~/.cache}/vgi-translate-notebooks/<manifest-SHA256>`, and rechecks installed file hashes on every run. It refuses a corrupt cache or changed package instead of silently replacing data. No model weights are committed. The model URL was verified with an identifying notebook User-Agent; an initial default urllib request returned HTTP403, while the explicitly identified public download succeeded with the pinned bytes.

Setup points `ARGOS_PACKAGES_DIR` at that private cache and explicitly selects Argos, CPU float32, the pinned Stanza tokenizer assets and local resource index and beam size 4. Existing global language packages or settings are not needed. The notebook restores its environment at cleanup. Models and language detection run in the worker process; only setup downloads assets. The native Haybarn connection also uses an empty temporary secret directory with persistent secrets disabled.

Model attribution from the package: **Jörg Tiedemann and Santhosh Thottingal**, “OPUS-MT — Building open translation services for the World,” Proceedings of the 22nd Annual Conference of the European Association for Machine Translation (EAMT), Lisbon, 2020. The package states that its original OPUS model is licensed **CC-BY 4.0**. Argos software and the worker have their own licenses; see the upstream package attribution and repository LICENSE.

## What the experiment establishes

All 15 messages are authored examples with no customer or private data. `MIN_CHARS` is a trimmed Unicode-character threshold (1–30), default 20, experiment 5. Only detected English/Spanish rows that clear the length policy enter the worker's batch translation; unsupported codes stay visible for review. The pipeline preserves originals and IDs and separates missing, blank, held and processed results. Short-text language codes can be surprising; the worker exposes no calibrated confidence score. String-length changes are not semantic-quality measurements, and the corpus proportions do not represent a production workload.

The experiment changes eligibility while preserving the corpus/detection fingerprint, pinned model and outputs of rows admitted in both runs. It does not validate an optimal threshold or translation accuracy. See [STANDARD.md](STANDARD.md).

Repository checks pass: 37 pytest tests, 94 stdio / 106 HTTP / 94 Unix SQL assertions across six source cases, Ruff lint/format, mypy (9 source files), isolated pydoclint, and metadata quality 100/100 L2 with zero findings. The runtime-resource refresh issue above was found and resolved within notebook setup; worker source and locks remain unchanged.

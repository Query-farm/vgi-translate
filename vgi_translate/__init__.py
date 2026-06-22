"""Local neural machine translation as a VGI worker: scalars + a batched table function.

The implementation is split so each concern stays focused:

- ``backend``    -- pluggable translation backend (Argos Translate by default),
  language detection, and the per-process model/package cache.
- ``scalars``    -- ``translate`` and ``detect_lang`` scalar functions.
- ``tables``     -- ``translate_all`` batched table-in-out function with ``id``
  passthrough.

``translate_worker.py`` at the repo root assembles these into the ``translate``
catalog and runs the worker.

Licensing note: the default backend is **Argos Translate** (MIT), which downloads
permissively-licensed OPUS-MT language packages on demand. See the README for the
NLLB-200 (CC-BY-NC) caveat and how to opt into other backends at your own
licensing risk.
"""

from __future__ import annotations

__version__ = "0.1.0"

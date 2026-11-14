"""Install one SHA256-pinned Argos package into a private notebook cache."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen


def digest(path):
    """Hash a file without reading the whole model into memory."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare_model():
    """Verify an existing model or atomically download/extract the exact package."""
    manifest = json.loads(Path("model-package.json").read_text())
    base = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "vgi-translate-notebooks"
    base.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    cache = base / cache_key
    lock = base / (cache_key + ".lock")
    deadline = time.monotonic() + 180
    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            if time.monotonic() > deadline:
                raise TimeoutError(f"Model cache lock timed out: {lock}") from None
            time.sleep(0.2)
    try:
        if cache.exists():
            if not all(
                (cache / name).is_file() and digest(cache / name) == expected
                for name, expected in manifest["runtime_files"].items()
            ):
                raise ValueError(f"Model cache verification failed: {cache}")
            return cache, manifest
        with tempfile.TemporaryDirectory(prefix="model-stage-", dir=base) as tmp:
            stage = Path(tmp)
            archive = stage / "package.argosmodel"
            request = Request(
                manifest["url"],
                headers={
                    "User-Agent": "vgi-translate-notebooks/1.0 (+https://github.com/Query-farm/vgi-translate)"
                },
            )
            with urlopen(request, timeout=60) as response, archive.open("wb") as output:
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > manifest["bytes"]:
                        raise ValueError("Model response exceeds pinned size")
                    output.write(chunk)
            if size != manifest["bytes"] or digest(archive) != manifest["sha256"]:
                raise ValueError("Model package hash/size mismatch; no fallback")
            extracted = stage / "packages"
            extracted.mkdir()
            with zipfile.ZipFile(archive) as zipped:
                names = {i.filename for i in zipped.infolist() if not i.is_dir()}
                if names != set(manifest["files"]):
                    raise ValueError("Unexpected model archive contents")
                for name in names:
                    if Path(name).is_absolute() or ".." in Path(name).parts:
                        raise ValueError("Invalid archive path")
                    target = extracted / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zipped.open(name) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
                    if digest(target) != manifest["files"][name]:
                        raise ValueError("Model member hash mismatch")
            for asset in manifest["runtime_assets"]:
                target = extracted / asset["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                request = Request(asset["url"], headers={"User-Agent": "vgi-translate-notebooks/1.0"})
                with urlopen(request, timeout=60) as response:
                    payload = response.read(asset["bytes"] + 1)
                if len(payload) != asset["bytes"] or hashlib.sha256(payload).hexdigest() != asset["sha256"]:
                    raise ValueError("Tokenizer asset hash/size mismatch; no fallback")
                target.write_bytes(payload)
            extracted.replace(cache)
        return cache, manifest
    finally:
        lock.rmdir()


class ResourceManifestServer:
    """Serve only the pinned Stanza 1.10.0 index, preventing an online refresh."""

    def __init__(self, model_dir, manifest, artifact_dir):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        member = "translate-es_en-1_9/stanza/resources.json"
        body = (model_dir / member).read_bytes()
        expected = manifest["runtime_files"][member]
        if hashlib.sha256(body).hexdigest() != expected:
            raise ValueError("Pinned Stanza index hash mismatch")
        artifact_dir.mkdir(exist_ok=True)
        self.requests = []
        self.lock = threading.Lock()
        owner = self
        audit = artifact_dir / "resource-requests.json"
        audit.write_text("[]\n")

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_GET(self):
                with owner.lock:
                    status = 200 if self.path == "/resources_1.10.0.json" and len(owner.requests) < 4 else 400
                    owner.requests.append(
                        {"path": self.path, "status": status, "sha256": expected if status == 200 else None}
                    )
                    staged = audit.with_suffix(".tmp")
                    staged.write_text(json.dumps(owner.requests, indent=2))
                    staged.replace(audit)
                if status != 200:
                    self.send_error(status, "Outside pinned local Stanza resource budget")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def close(self):
        """Stop this run's owned loopback endpoint."""
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

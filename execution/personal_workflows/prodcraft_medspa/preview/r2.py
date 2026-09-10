"""
r2.py
description: S3-compatible SigV4 client for Cloudflare R2 (stdlib hmac/hashlib over requests, no boto3),
    plus MockR2 (local-dir backed, same interface) for --mock runs.
inputs: Imported by build_preview.py/takedown.py. Env R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY,
    CLOUDFLARE_ACCOUNT_ID, R2_BUCKET (live only). Standalone CLI: --selftest.
outputs: R2Client.upload_dir/delete_prefix make HTTPS calls to R2; MockR2 writes/deletes under a local dir.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import shutil
import threading
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode, urlsplit

import requests

_S3_NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
_EMPTY_PAYLOAD_SHA256 = hashlib.sha256(b"").hexdigest()

CONTENT_TYPES: dict[str, str] = {
    "html": "text/html; charset=utf-8",
    "css": "text/css; charset=utf-8",
    "js": "application/javascript; charset=utf-8",
    "json": "application/json; charset=utf-8",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "svg": "image/svg+xml",
    "ico": "image/x-icon",
    "woff2": "font/woff2",
    "txt": "text/plain; charset=utf-8",
    "xml": "application/xml; charset=utf-8",
}


def content_type_for(path: str) -> str:
    """Content-Type by file extension, mirroring preview/worker/src/index.ts's CONTENT_TYPES table."""
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return CONTENT_TYPES.get(ext, "application/octet-stream")


# ---------------------------------------------------------------------------
# AWS SigV4, implemented against stdlib hmac/hashlib only (no boto3).
# ---------------------------------------------------------------------------


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret_key: str, date_stamp: str, region: str, service: str) -> bytes:
    k_date = _hmac_sha256(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _hmac_sha256(k_date, region)
    k_service = _hmac_sha256(k_region, service)
    return _hmac_sha256(k_service, "aws4_request")


def sign_request(
    method: str,
    url: str,
    headers: dict[str, str],
    payload: bytes,
    access_key: str,
    secret_key: str,
    region: str = "auto",
    service: str = "s3",
    amz_datetime: datetime | None = None,
) -> dict[str, str]:
    """Return `headers` (lower-cased keys) plus host/x-amz-date/x-amz-content-sha256/Authorization added.

    Deterministic for a fixed `amz_datetime` — pass one explicitly in tests instead of relying on "now".
    Canonical-request construction follows the AWS SigV4 spec: METHOD\\nURI\\nQUERY\\nHEADERS\\n\\nSIGNED\\nHASH.
    """
    parsed = urlsplit(url)
    host = parsed.netloc
    canonical_uri = parsed.path or "/"
    # Query params must be URI-encoded and sorted by key for the canonical request.
    query_pairs = sorted(
        (k, v) for k, v in [p.split("=", 1) if "=" in p else (p, "") for p in parsed.query.split("&") if p]
    )
    canonical_querystring = "&".join(f"{k}={v}" for k, v in query_pairs)

    now = amz_datetime or datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    payload_hash = _sha256_hex(payload)

    norm_headers = {k.lower(): str(v).strip() for k, v in headers.items()}
    norm_headers["host"] = host
    norm_headers["x-amz-content-sha256"] = payload_hash
    norm_headers["x-amz-date"] = amz_date

    sorted_names = sorted(norm_headers)
    canonical_headers = "".join(f"{name}:{norm_headers[name]}\n" for name in sorted_names)
    signed_headers = ";".join(sorted_names)

    canonical_request = "\n".join(
        [method, canonical_uri, canonical_querystring, canonical_headers, signed_headers, payload_hash]
    )
    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(
        ["AWS4-HMAC-SHA256", amz_date, credential_scope, _sha256_hex(canonical_request.encode("utf-8"))]
    )
    signing_key = _signing_key(secret_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    norm_headers["Authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return norm_headers


# ---------------------------------------------------------------------------
# R2Client — live S3-compatible client over `requests`.
# ---------------------------------------------------------------------------


class R2Client:
    """S3-compatible client for one R2 bucket, signed with SigV4 (region 'auto', service 's3')."""

    def __init__(self, account_id: str, access_key: str, secret_key: str, bucket: str):
        self.endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket = bucket
        self.region = "auto"
        self.service = "s3"

    def _url(self, key: str = "") -> str:
        base = f"{self.endpoint}/{self.bucket}"
        if not key:
            return base
        return f"{base}/{quote(key, safe='/~')}"

    def _request(
        self,
        method: str,
        key: str = "",
        params: dict[str, str] | None = None,
        body: bytes = b"",
        extra_headers: dict[str, str] | None = None,
    ) -> requests.Response:
        url = self._url(key)
        if params:
            url = f"{url}?{urlencode(sorted(params.items()))}"
        signed = sign_request(method, url, extra_headers or {}, body, self.access_key, self.secret_key, self.region, self.service)
        resp = requests.request(method, url, headers=signed, data=body, timeout=30)
        resp.raise_for_status()
        return resp

    def upload_bytes(self, key: str, data: bytes, content_type: str | None = None) -> None:
        headers = {"content-type": content_type or content_type_for(key)}
        self._request("PUT", key, body=data, extra_headers=headers)

    def upload_file(self, local_path: str | Path, key: str, content_type: str | None = None) -> None:
        self.upload_bytes(key, Path(local_path).read_bytes(), content_type=content_type)

    def upload_dir(self, local_dir: str | Path, prefix: str, workers: int = 6) -> dict[str, int]:
        """Upload every file under `local_dir` to `{prefix}/{relative path}`, 6-wide by default."""
        local_dir = Path(local_dir)
        files = [p for p in local_dir.rglob("*") if p.is_file()]
        counters = {"uploaded": 0, "errors": 0}
        lock = threading.Lock()  # counters are read-modify-write across threads — see python-hardening.md #2
        errors: list[str] = []

        def _one(path: Path) -> None:
            rel = path.relative_to(local_dir).as_posix()
            key = f"{prefix.rstrip('/')}/{rel}"
            try:
                self.upload_file(path, key)
                with lock:
                    counters["uploaded"] += 1
            except Exception as exc:  # noqa: BLE001 — collected per-file, reported once after the pool drains
                with lock:
                    counters["errors"] += 1
                    errors.append(f"{rel}: {exc}")

        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(_one, files))

        if errors:
            raise RuntimeError(f"r2 upload_dir: {len(errors)} file(s) failed: {'; '.join(errors[:5])}")
        return counters

    def list_objects(self, prefix: str) -> list[str]:
        keys: list[str] = []
        continuation: str | None = None
        while True:
            params = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
            if continuation:
                params["continuation-token"] = continuation
            resp = self._request("GET", params=params)
            root = ET.fromstring(resp.content)
            for contents in root.findall("s3:Contents", _S3_NS):
                key_el = contents.find("s3:Key", _S3_NS)
                if key_el is not None and key_el.text:
                    keys.append(key_el.text)
            truncated = (root.findtext("s3:IsTruncated", default="false", namespaces=_S3_NS) or "false").lower()
            if truncated == "true":
                continuation = root.findtext("s3:NextContinuationToken", namespaces=_S3_NS)
                if not continuation:
                    break
            else:
                break
        return keys

    def delete_object(self, key: str) -> None:
        self._request("DELETE", key)

    def delete_prefix(self, prefix: str) -> int:
        keys = self.list_objects(prefix)
        for key in keys:
            self.delete_object(key)
        return len(keys)


# ---------------------------------------------------------------------------
# MockR2 — local-dir backed, same interface, used under --mock.
# ---------------------------------------------------------------------------


class MockR2:
    """Local-filesystem stand-in for R2Client. Writes under `root`; same method surface as R2Client."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, key: str) -> Path:
        # key may derive from an LLM-influenced slug; resolve + boundary-check per python-hardening.md #3.
        resolved = (self.root / key).resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError(f"path traversal blocked for key: {key}")
        return resolved

    def upload_bytes(self, key: str, data: bytes, content_type: str | None = None) -> None:
        dest = self._safe_path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    def upload_file(self, local_path: str | Path, key: str, content_type: str | None = None) -> None:
        self.upload_bytes(key, Path(local_path).read_bytes())

    def upload_dir(self, local_dir: str | Path, prefix: str, workers: int = 6) -> dict[str, int]:
        local_dir = Path(local_dir)
        count = 0
        for path in local_dir.rglob("*"):
            if path.is_file():
                rel = path.relative_to(local_dir).as_posix()
                self.upload_file(path, f"{prefix.rstrip('/')}/{rel}")
                count += 1
        return {"uploaded": count, "errors": 0}

    def list_objects(self, prefix: str) -> list[str]:
        base = self._safe_path(prefix)
        if not base.exists():
            return []
        return [str(p.relative_to(self.root).as_posix()) for p in base.rglob("*") if p.is_file()]

    def delete_prefix(self, prefix: str) -> int:
        base = self._safe_path(prefix)
        n = sum(1 for p in base.rglob("*") if p.is_file()) if base.exists() else 0
        if base.exists():
            shutil.rmtree(base, ignore_errors=True)
        return n


def _sigv4_selftest() -> dict[str, Any]:
    """Determinism + header-set check (no live AWS/R2 credentials required, no network call)."""
    fixed_dt = datetime(2013, 5, 24, 0, 0, 0, tzinfo=timezone.utc)
    args = (
        "GET",
        "https://examplebucket.s3.amazonaws.com/test.txt",
        {"range": "bytes=0-9"},
        b"",
        "AKIAIOSFODNN7EXAMPLE",
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "us-east-1",
        "s3",
        fixed_dt,
    )
    headers_a = sign_request(*args)
    headers_b = sign_request(*args)
    deterministic = headers_a["Authorization"] == headers_b["Authorization"]
    expected_header_set = {"range", "host", "x-amz-content-sha256", "x-amz-date", "Authorization"}
    has_expected_headers = expected_header_set.issubset(headers_a.keys())
    return {
        "deterministic": deterministic,
        "has_expected_headers": has_expected_headers,
        "authorization": headers_a["Authorization"],
    }


def main() -> None:
    """description: SigV4 self-test (determinism + header set) — no network, no credentials required.
    inputs: --selftest.
    outputs: stdout JSON {"script": "r2", "deterministic": bool, "has_expected_headers": bool}.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true", help="Run the SigV4 determinism/header-set self-test")
    args = parser.parse_args()

    if args.selftest:
        result = _sigv4_selftest()
        print(json.dumps({"script": "r2", **result}))
        return

    parser.print_help()


if __name__ == "__main__":
    main()

"""Localhost server that assembles a page per request with Jev.

description: stdlib http.server on 127.0.0.1. GET / builds the visitor context from the
             real request (User-Agent -> device, Referer, Accept-Language -> locale,
             utm_* query, cookie jev_seen -> returning) and serves the assembled page;
             ?debug=1 adds a ribbon with choices, latency and cost. GET /preview?persona=X
             renders a built-in persona from personas.json.
inputs: --port (default 8766), --brand-json, --cache-file (default .tmp/jev_pages_cache.json).
        env OPENROUTER_API_KEY (or alias).
outputs: HTML responses; sets cookie jev_seen=1.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from execution.content.jev_page_assembler import assembler  # noqa: E402

MOBILE_HINTS = ("mobi", "android", "iphone", "ipod", "windows phone")
TABLET_HINTS = ("ipad", "tablet")


def device_from_ua(ua: str) -> str:
    u = (ua or "").lower()
    if any(h in u for h in TABLET_HINTS):
        return "tablet"
    if any(h in u for h in MOBILE_HINTS):
        return "mobile"
    return "desktop"


def visitor_from_request(headers: Any, path: str, now_hour: int | None = None) -> dict[str, Any]:
    q = parse_qs(urlparse(path).query)
    first = lambda k: (q.get(k) or [""])[0]  # noqa: E731
    cookie = SimpleCookie()
    try:
        cookie.load(headers.get("Cookie", "") or "")
    except Exception:  # malformed cookie header from client; treat as no cookie
        cookie = SimpleCookie()
    lang = (headers.get("Accept-Language", "") or "en").split(",")[0].strip() or "en"
    hour = first("hour")
    return {
        "referrer": headers.get("Referer", "") or "",
        "utm_source": first("utm_source"), "utm_campaign": first("utm_campaign"),
        "device": device_from_ua(headers.get("User-Agent", "")),
        "locale": lang,
        "hour_local": int(hour) if hour.isdigit() else (now_hour if now_hour is not None else time.localtime().tm_hour),
        "returning": "jev_seen" in cookie,
        "pages_seen": [], "query_terms": first("q") or first("utm_term"),
    }


def make_handler(brand: dict[str, Any], library: dict[str, Any], cache_file: Path | None):
    personas = assembler.load_personas()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: str, ctype: str = "text/html; charset=utf-8") -> None:
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Set-Cookie", "jev_seen=1; Path=/; Max-Age=2592000; SameSite=Lax")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            u = urlparse(self.path)
            q = parse_qs(u.query)
            debug = (q.get("debug") or ["0"])[0] == "1"
            if u.path == "/":
                visitor = visitor_from_request(self.headers, self.path)
            elif u.path == "/preview":
                name = (q.get("persona") or [""])[0]
                if name not in personas:
                    self._send(404, "unknown persona; one of: " + ", ".join(personas), "text/plain; charset=utf-8")
                    return
                visitor = personas[name]
                debug = debug or "debug" not in q
            else:
                self._send(404, "not found", "text/plain; charset=utf-8")
                return
            res = assembler.assemble(visitor, brand, library, debug=debug, cache_file=cache_file)
            self._send(200, res["html"])

        def log_message(self, fmt: str, *args: Any) -> None:
            sys.stderr.write("[jev-pages] " + (fmt % args) + "\n")

    return Handler


def make_server(port: int, brand: dict[str, Any] | None = None,
                cache_file: Path | None = None) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", port),
                               make_handler(brand or assembler.DEFAULT_BRAND,
                                            assembler.load_library(), cache_file))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--brand-json", help="JSON file {name, product, audience}")
    ap.add_argument("--cache-file", default=str(assembler.DEFAULT_CACHE_FILE))
    a = ap.parse_args()
    brand = json.loads(Path(a.brand_json).read_text(encoding="utf-8")) if a.brand_json else None
    srv = make_server(a.port, brand, Path(a.cache_file) if a.cache_file else None)
    print(f"Jev page assembler on http://127.0.0.1:{a.port}/  (try /?debug=1 or /preview?persona=linkedin-cto)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass  # normal Ctrl-C shutdown
    return 0


if __name__ == "__main__":
    sys.exit(main())

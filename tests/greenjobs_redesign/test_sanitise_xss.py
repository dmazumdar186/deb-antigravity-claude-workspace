"""build_site.sanitise_html: the Worker's sanitiser fix, ported (integration gap f, 2026-11-20).

description: One clean_tag pass let "<a<x> onmouseover=alert(1)>" splice into "<a onmouseover=...>" on the
    static boards (the Worker already looped until stable). These tests run the same hostile inputs as
    tests/greenjobs_redesign/platform/sanitise.test.mjs through the Python sanitiser and assert no event
    handler, script URL or open tag survives, then assert Python and the Worker produce identical output.
inputs: none (node on PATH for the parity check)
outputs: pytest result
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(
    0, str(REPO / "execution" / "gtm_client_workflows" / "greenjobs_redesign")
)
import build_site as b  # noqa: E402

BASE = "https://greenjobs.ie/ie/jobs/x/"
HOSTILE = [
    "<script>alert(1)</script>",
    "<script src=//evil.example/x.js>",
    "<img src=x onerror=alert(1)>",
    "<img src=x onerror=alert(1)",
    '<p onclick="alert(1)" style="x">t</p>',
    '<a href="javascript:alert(1)">x</a>',
    '<a href="  JaVaScRiPt:alert(1)">x</a>',
    '<a href="&#106;avascript:alert(1)">x</a>',
    '<a href="data:text/html;base64,PHNjcmlwdD4=">x</a>',
    "<svg onload=alert(1)><circle/></svg>",
    "<a<x> onmouseover=alert(1)>hover</a>",
    "<p<b> onclick=alert(1)>t</p>",
    "<a<<x>> onfocus=alert(1) autofocus>z</a>",
    "<scr<script>ipt>alert(1)</scr</script>ipt>",
    "<p>ok</p><img src=x onerror=alert(1) ",
    "<form action=//evil><input name=q></form>",
    '<div style="background:url(javascript:alert(1))">x</div>',
    "<!-- <script>alert(1)</script> --><p>after</p>",
]
UNSAFE = re.compile(r"\son[a-z]+\s*=|javascript:|vbscript:|data:text|style\s*=", re.I)


@pytest.mark.parametrize("markup", HOSTILE)
def test_no_handler_script_or_open_tag_survives(markup: str) -> None:
    out = b.sanitise_html(markup, BASE)
    for tag in re.findall(r"<[^>]*>", out):
        assert not UNSAFE.search(tag), f"{markup!r} -> {out!r}"
    assert not re.search(r"<(script|iframe|img|svg)", out, re.I), out
    assert not re.search(r"<[a-z][^>]*\Z", out, re.I), f"open tag left: {out!r}"


def test_the_reported_splice_is_closed() -> None:
    assert (
        b.sanitise_html("<a<x> onmouseover=alert(1)>hover</a>", BASE) == "<a>hover</a>"
    )


def test_ordinary_html_unchanged_by_the_loop() -> None:
    assert b.sanitise_html(
        '<p>See <a href="/about">us</a></p>', "https://greenjobs.ie/"
    ) == (
        '<p>See <a href="https://greenjobs.ie/about" rel="noopener nofollow">us</a></p>'
    )
    assert b.sanitise_html("<p>a &lt; b &amp; c</p>", BASE) == "<p>a &lt; b &amp; c</p>"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")
def test_python_and_worker_sanitisers_agree() -> None:
    mod = (
        REPO
        / "execution/gtm_client_workflows/greenjobs_redesign/platform_worker/src/render/sanitise.js"
    ).as_uri()
    script = (
        f"import {{ sanitiseHtml }} from {json.dumps(mod)};"
        "const xs = JSON.parse(process.argv[1]);"
        f"process.stdout.write(JSON.stringify(xs.map((x) => sanitiseHtml(x, {json.dumps(BASE)}))));"
    )
    r = subprocess.run(
        ["node", "--input-type=module", "-e", script, json.dumps(HOSTILE)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=True,
    )
    worker = json.loads(r.stdout)
    assert [b.sanitise_html(x, BASE) for x in HOSTILE] == worker

"""Unit + integration tests for the Gaia Talent redesign build pipeline.

description: Exercises build_site.py helper functions in isolation (unit tier)
  and the build -> validate -> link-check chain against the real dataset and
  against deliberately injected faults (integration tier). Never touches
  deliverables/{src,site} — every build target is a fresh directory under
  this repo's .tmp/ (guard_output's allow-list dropped the blanket /tmp entry
  in round 4, so a bare system tempdir is refused).
inputs: none (reads the checked-in src/ tree read-only)
outputs: stdout PASS/FAIL lines; process exit code 0 (all pass) / 1 (failures)

Run: python3 -m pytest tests/gaia_redesign/test_build.py -v
     or: python3 tests/gaia_redesign/test_build.py
"""

from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO / "execution" / "gtm_client_workflows" / "gaia_redesign"
SRC = REPO / "deliverables" / "gaia_redesign_2026-09-17" / "src"

sys.path.insert(0, str(SCRIPT_DIR))
import build_site  # noqa: E402
import check_job_links  # noqa: E402
import validate_site  # noqa: E402

RESULTS: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> None:
    RESULTS.append((ok, label))
    print(("PASS  " if ok else "FAIL  ") + label)


# --------------------------------------------------------------- TIER 1: unit

def test_esc():
    check(build_site.esc('<b>"x"</b> & Y') == "&lt;b&gt;&quot;x&quot;&lt;/b&gt; &amp; Y", "esc: escapes <, >, &, \"")
    check(build_site.esc(5) == "5", "esc: coerces non-str to str first")
    check(build_site.esc("") == "", "esc: empty string stays empty")


def test_qs():
    out = build_site.qs("Energy & Utilities")
    check("&" not in out or "&amp;" in out, "qs: raw '&' never survives unescaped")
    check("%26" in out, "qs: '&' is percent-encoded before HTML-escaping")
    # round trip: unquoting the unescaped value should recover the original
    import html as _html
    from urllib.parse import unquote
    check(unquote(_html.unescape(out)) == "Energy & Utilities", "qs: round-trips through unquote(unescape())")


def test_json_ld_escaping():
    payload = {"title": "</script><script>alert(1)</script>", "line": "a b c"}
    out = build_site.json_ld(payload)
    check("</script>" not in out, "json_ld: literal </script> is neutralised")
    check(" " not in out and " " not in out, "json_ld: U+2028/U+2029 are escaped")
    check(json.loads(out.replace("\\u003c", "<")) is not None, "json_ld: output round-trips through json.loads")


def _job(**over):
    base = {
        "slug": "a-role", "title": "Ecologist", "url": "https://gaiatalent.com/jobs/a-role/",
        "location": "Dublin", "type": "Permanent", "sectors": ["Conservation"], "summary": "x",
    }
    base.update(over)
    return base


def test_check_dataset():
    ok_jobs = [_job()]
    check(build_site.check_dataset(ok_jobs) == [], "check_dataset: a well-formed job has no problems")

    missing = [_job(title="")]
    problems = build_site.check_dataset(missing)
    check(any("missing required key" in p for p in problems), "check_dataset: catches a missing required key")

    bad_url = [_job(url="ftp://example.com/x")]
    check(any("not http(s)" in p for p in build_site.check_dataset(bad_url)), "check_dataset: rejects a non-http(s) url")

    no_sectors = [_job(sectors=[])]
    check(any("non-empty list" in p for p in build_site.check_dataset(no_sectors)), "check_dataset: rejects empty sectors")

    dup = [_job(slug="x"), _job(slug="x")]
    check(any("duplicate slug" in p for p in build_site.check_dataset(dup)), "check_dataset: catches a duplicate slug")


def test_sector_keys_and_count():
    j = _job(sectors=["Water & Flood Risk", " Energy "])
    check(build_site.sector_keys(j) == ["water & flood risk", "energy"], "sector_keys: lower-cased and stripped")
    jobs = [_job(sectors=["Energy"]), _job(slug="b", sectors=["Energy", "Water"]), _job(slug="c", sectors=["Water"])]
    check(build_site.sector_count(jobs, "energy") == 2, "sector_count: counts case-insensitively")
    check(build_site.sector_count(jobs, "Water & Flood Risk") == 0, "sector_count: no match returns 0, not an error")


def test_sector_options_and_chips():
    jobs = [_job(sectors=["Energy"]), _job(slug="b", sectors=["energy", "Water"])]
    opts = build_site.sector_options(jobs)
    check(opts == ["Energy"] or opts == ["Water", "Energy"] or sorted(opts) == sorted(["Energy", "Water"]),
          "sector_options: de-duplicates case-insensitively, keeps a display form")
    chips_html = build_site.render_chips(jobs)
    check("<div class=\"chips\">" in chips_html, "render_chips: wraps chips in the expected container")
    check("%26" in build_site.render_chips([_job(sectors=["A & B"])]), "render_chips: '&' in a sector name is percent-encoded in the href")


def test_job_haystack_and_sector_map_term():
    jobs = [_job(title="Senior Hydrogeologist"), _job(slug="b", title="Wind Consents Officer")]
    count, term = build_site.sector_map_term(["hydro", "wind", "consents"], jobs)
    check(count >= 1, "sector_map_term: finds at least one keyword hit across the two jobs")
    check(term in ("hydro", "wind", "consents"), "sector_map_term: returns one of the supplied keywords")


def test_measure(tmp_root: Path):
    f = tmp_root / "measure.txt"
    f.write_text("a" * 5000, encoding="utf-8")
    raw, gz = build_site._measure(f)
    check(raw == 5000, "_measure: raw byte count matches file size")
    check(0 < gz < raw, "_measure: gzip of repetitive text is smaller than raw")
    raw2, gz2 = build_site._measure(f)
    check((raw2, gz2) == (raw, gz), "_measure: cached result is stable across repeat calls")


def test_publish_text_strips_block_comments_only():
    src = "/* header\n   comment */\n.a { color: red; } // not a comment (kept)\nvar re = /a\\/\\/b/;\n"
    out = build_site.publish_text(src)
    check("/* header" not in out, "publish_text: strips a block comment")
    check("// not a comment (kept)" in out, "publish_text: leaves a trailing // alone (could be a URL/regex)")


def test_run_node_tests_never_reports_zero_as_passing(tmp_root: Path):
    # Item 1: a (0, 0) node --test summary, or a non-zero exit with no "# fail"
    # line, must never come back as a clean pass.
    src = tmp_root / "node_tests_crash"
    (src / "js").mkdir(parents=True)
    (src / "js" / "motion.test.js").write_text("throw new Error('boom');\n", encoding="utf-8")
    result = build_site.run_node_tests(src)
    check(
        result is not None and result[1] > 0,
        f"run_node_tests: a crashing test file (non-zero exit, no '# fail' line) is reported as a failure (got {result})",
    )

    with mock.patch("subprocess.run") as m:
        m.return_value = mock.Mock(returncode=0, stdout="# pass 0\n# fail 0\n")
        src2 = tmp_root / "node_tests_zero_summary"
        (src2 / "js").mkdir(parents=True)
        (src2 / "js" / "motion.test.js").write_text("", encoding="utf-8")
        result2 = build_site.run_node_tests(src2)
    check(
        result2 is not None and result2[1] > 0,
        f"run_node_tests: a clean-exit (0, 0) summary is still reported as a failure (got {result2})",
    )


def test_check_dataset_rejects_pipe_in_sector(tmp_root: Path):
    # Item 3: '|' in a sector collides with data-sector's '|'-joined encoding.
    bad = [_job(sectors=["Water | Flood"])]
    problems = build_site.check_dataset(bad)
    check(any("'|'" in p for p in problems), "check_dataset: rejects '|' inside a sector name")


def test_check_job_links_flags_redirect_as_inconclusive():
    # Item 4: urlopen follows redirects itself, so a redirected URL comes back
    # with a 200 from the final page; geturl() differing from the requested
    # URL is the only way to still see it, and it must be "inconclusive", not
    # "ok" (the live link we published is not the one that answered).
    class _Resp:
        status = 200
        def getcode(self): return 200
        def geturl(self): return "https://gaiatalent.com/jobs/actually-moved/"
        def __enter__(self): return self
        def __exit__(self, *a): return False

    with mock.patch("urllib.request.urlopen", return_value=_Resp()):
        row = check_job_links.check_one("https://gaiatalent.com/jobs/old-slug/")
    check(row["verdict"] == "inconclusive", f"check_job_links: a redirected URL is 'inconclusive', not 'ok' (got {row['verdict']!r})")
    check(not row["ok"], "check_job_links: a redirected URL's ok flag is False")


def test_validate_site_forbidden_words_round4():
    # Item 5: the four words/patterns round 4 added to FORBIDDEN.
    import re as _re
    for phrase in ("Hidden Depth", "615983", "our CRO", "built on WordPress"):
        text = f"some text {phrase} on the page"
        hit = any(_re.search(pattern, text) for pattern, _ in validate_site.FORBIDDEN)
        check(hit, f"validate_site.FORBIDDEN: matches {phrase!r}")


def test_main_js_clears_stack_inert_outside_desktop_motion():
    # Item 7: main.js's update() must have a branch that clears inert/
    # aria-hidden on the stack cards when not painting the desktop stack.
    text = (SRC / "js" / "main.js").read_text(encoding="utf-8")
    check("el.inert = false" in text, "main.js: update() clears card.inert outside desktop-motion mode")
    check("removeAttribute('aria-hidden')" in text, "main.js: update() removes aria-hidden outside desktop-motion mode")


def test_jobs_js_syncurl_preserves_hash():
    # Item 8: syncUrl must not drop location.hash when it rewrites the query string.
    text = (SRC / "js" / "jobs.js").read_text(encoding="utf-8")
    check("window.location.hash" in text, "jobs.js: syncUrl reads location.hash")
    check("+ hash)" in text or "+hash)" in text, "jobs.js: syncUrl appends hash back onto the replaceState URL")


def test_guard_output(tmp_root: Path):
    msg = build_site.guard_output(SRC, SRC)
    check(bool(msg), "guard_output: refuses --out == --src")
    msg2 = build_site.guard_output(SRC, Path("/etc"))
    check(bool(msg2), "guard_output: refuses an --out outside the allowed build areas")
    ok_out = tmp_root / "guard_ok"
    check(build_site.guard_output(SRC, ok_out) == "", "guard_output: allows a fresh dir under an allowed base (/tmp)")
    nonempty = tmp_root / "guard_nonempty"
    nonempty.mkdir()
    (nonempty / "keep.txt").write_text("x", encoding="utf-8")
    check(bool(build_site.guard_output(SRC, nonempty)), "guard_output: refuses a non-empty dir with no .gaia-build marker")
    (nonempty / ".gaia-build").write_text("x", encoding="utf-8")
    check(build_site.guard_output(SRC, nonempty) == "", "guard_output: allows a non-empty dir that carries the marker")


# ---------------------------------------------------------- TIER 2: integration

def test_integration_build_validate_linkcheck_stubbed(tmp_root: Path):
    # A copy of src/ so the stubbed link-check run never writes into the real
    # deliverables/src/data/link_check.json (src/ is never modified by tests).
    out = tmp_root / "site_stub"
    src_copy = tmp_root / "src_linkcheck_stub"
    shutil.copytree(SRC, src_copy)

    class _Resp:
        def __init__(self, url):
            self._url = url
        status = 200
        def getcode(self): return 200
        def geturl(self): return self._url  # same URL requested: not a redirect
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def _fake_urlopen(req, timeout=None):
        return _Resp(req.full_url if hasattr(req, "full_url") else req)

    with mock.patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        rc = build_site.build(src_copy, out, skip_links=False)
    check(rc == 0, "integration: build() returns 0 against the real dataset with urlopen stubbed 200")
    check((out / "index.html").exists(), "integration: index.html was written")
    check((out / "jobs" / "index.html").exists(), "integration: jobs/index.html was written")
    check((out / "for-keith" / "index.html").exists(), "integration: for-keith/index.html was written")
    link_report = json.loads((src_copy / "data" / "link_check.json").read_text(encoding="utf-8"))
    check(link_report["ok"] == link_report["total"], "integration: stubbed 200s mark every role URL as ok")


def test_integration_build_skip_links_real_dataset(tmp_root: Path):
    out = tmp_root / "site_real"
    rc = build_site.build(SRC, out, skip_links=True)
    check(rc == 0, "integration: build() --skip-links returns 0 on the real, unmodified dataset")
    jobs = json.loads((SRC / "data" / "jobs.json").read_text(encoding="utf-8"))
    fails = validate_site.validate(out, jobs)
    check(fails == [], f"integration: validate_site.validate() finds 0 problems on a clean build (got {fails[:3]})")


# The real dataset (not a hand-built stub): build() requires one live match per
# FLOW_PICKS hero state, which a two-job fixture cannot satisfy.
FAULT_JOBS_BASE = json.loads((SRC / "data" / "jobs.json").read_text(encoding="utf-8"))


def _built_site_with(tmp_root: Path, tag: str, jobs, html_patch=None) -> tuple[Path, list[str]]:
    """Build `jobs` into a throwaway site, optionally corrupt one HTML file after
    the fact (html_patch: (relpath, fn(text)->text)), then validate it."""
    out = tmp_root / f"fault_{tag}"
    src_copy = tmp_root / f"src_{tag}"
    shutil.copytree(SRC, src_copy)
    (src_copy / "data" / "jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
    (src_copy / "data" / "link_check.json").write_text(
        json.dumps({"total": len(jobs), "ok": len(jobs), "skipped": True, "checked_on": "2026-09-17"}), encoding="utf-8"
    )
    rc = build_site.build(src_copy, out, skip_links=True)
    if rc != 0 or html_patch is None:
        return out, ([] if rc == 0 else ["build itself failed (rc=%d) before validation could run" % rc])
    rel, fn = html_patch
    target = out / rel
    target.write_text(fn(target.read_text(encoding="utf-8")), encoding="utf-8")
    fails = validate_site.validate(out, jobs)
    return out, fails


def test_validator_rejects_five_injected_faults(tmp_root: Path):
    # 1. leading-slash href
    _, fails = _built_site_with(
        tmp_root, "leadslash", FAULT_JOBS_BASE,
        ("index.html", lambda t: t.replace('href="jobs/index.html"', 'href="/jobs/index.html"', 1)),
    )
    check(any("absolute path" in f for f in fails), "validator: catches a leading-slash href")

    # 2. missing image
    _, fails = _built_site_with(
        tmp_root, "missingimg", FAULT_JOBS_BASE,
        ("index.html", lambda t: t.replace("</body>", '<img src="assets/does-not-exist.png" alt="x" width="1" height="1"></body>')),
    )
    check(any("does not resolve to a file" in f for f in fails), "validator: catches a missing image reference")

    # 3. forbidden word
    _, fails = _built_site_with(
        tmp_root, "forbidden", FAULT_JOBS_BASE,
        ("index.html", lambda t: t.replace("</body>", '<p>Built with AI assistance.</p></body>')),
    )
    check(any("forbidden word" in f for f in fails), "validator: catches a forbidden word (AI) on a public page")

    # 4. unknown job href on the board (not in the dataset)
    ghost = (
        '<a class="rolerow" data-job data-location="Dublin" data-sector="x" data-type="Permanent" '
        'href="https://gaiatalent.com/jobs/not-in-dataset/">ghost</a>'
    )
    _, fails = _built_site_with(
        tmp_root, "unknownjob", FAULT_JOBS_BASE,
        ("jobs/index.html", lambda t: t.replace("</main>", ghost + "</main>", 1)),
    )
    check(any("not in the dataset" in f for f in fails), "validator: catches a job link not present in the dataset")

    # 5. </script> in a title breaking out of the JSON-LD block. Round 4's
    # check_dataset now rejects any '<'/'>' in a title outright (belt as well
    # as the pre-existing json_ld() escaping), so this is caught before a
    # single file is rendered rather than after.
    evil_jobs = copy.deepcopy(FAULT_JOBS_BASE)
    evil_jobs[0]["title"] = 'Ecologist</script><script>alert(1)</script>'
    out, fails = _built_site_with(tmp_root, "scriptbreak", evil_jobs)
    check(not out.exists(), "build: a title containing '<'/'>' is rejected at the dataset stage, no output written")
    check(
        fails == ["build itself failed (rc=%d) before validation could run" % 2],
        f"build: rc=2 (dataset validation failure), not a render-then-validate pass (got {fails[:2]})",
    )


def test_dataset_problems_block_the_build(tmp_root: Path):
    out = tmp_root / "should_not_exist"
    src_copy = tmp_root / "src_baddata"
    shutil.copytree(SRC, src_copy)
    (src_copy / "data" / "jobs.json").write_text(json.dumps([_job(title="")]), encoding="utf-8")
    rc = build_site.build(src_copy, out, skip_links=True)
    check(rc == 2, "integration: a structurally invalid jobs.json makes build() fail fast (rc=2)")
    check(not out.exists(), "integration: no output directory is created when dataset validation fails")


# ------------------------------------------------------------------ runner

def main() -> int:
    import inspect
    base = REPO / ".tmp"
    base.mkdir(exist_ok=True)
    tmp_root = Path(tempfile.mkdtemp(prefix="gaia_test_build_", dir=str(base)))
    try:
        for name, fn in sorted(globals().items()):
            if not name.startswith("test_") or not callable(fn):
                continue
            sig = inspect.signature(fn)
            if "tmp_root" in sig.parameters:
                fn(tmp_root)
            else:
                fn()
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
    passed = sum(1 for ok, _ in RESULTS if ok)
    failed = [label for ok, label in RESULTS if not ok]
    print(f"\nUnit+Integration: {passed} passed, {len(failed)} failed")
    for label in failed:
        print(f"  FAIL: {label}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())


# ------------------------------------------------------------- pytest shim
# Allows `python3 -m pytest tests/gaia_redesign/test_build.py` to run the same
# checks with a real tmp_path fixture, without duplicating test bodies.
try:
    import pytest

    @pytest.fixture
    def tmp_root(tmp_path):
        return tmp_path

    def test_all_via_pytest(tmp_root):
        RESULTS.clear()
        import inspect
        for name, fn in sorted(globals().items()):
            if not name.startswith("test_") or fn in (test_all_via_pytest,):
                continue
            if name == "test_all_via_pytest":
                continue
            sig = inspect.signature(fn)
            if "tmp_root" in sig.parameters:
                fn(tmp_root)
            else:
                fn()
        failed = [label for ok, label in RESULTS if not ok]
        assert not failed, "failures: " + "; ".join(failed)
except ImportError:
    pass

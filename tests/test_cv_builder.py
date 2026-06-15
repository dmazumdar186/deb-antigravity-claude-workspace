"""Per-variant render tests for cv_builder, cv_builder_en, cv_builder_skott.

The cv_builder family is a reportlab PDF generator with hardcoded content
(no LLM). The bar per ~/.claude/rules/front-door-synthetic.md still applies:
each variant must produce a PDF that

  - exists and is non-empty,
  - is exactly 2 pages (the operator's hard requirement),
  - contains the expected locale signal (FR/EN keyword),
  - contains the operator's name on at least one page.

Tests run the CLI as a subprocess so they exercise the actual entry-point.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]
PY = sys.executable

VARIANTS = [
    # (script_relpath, lang, lang_marker_substrings, cli_style)
    # cli_style: "company_role" -> --company X --role Y
    #            "output_only"  -> --output PATH
    # Marker match is case-insensitive substring (headers are commonly all-caps).
    (
        "execution/personal_workflows/cv_builder.py",
        "fr",
        ("expérience", "compétence", "formation", "résultats"),
        "company_role",
    ),
    (
        "execution/personal_workflows/cv_builder_en.py",
        "en",
        ("experience", "skills", "education", "results"),
        "company_role",
    ),
    (
        "execution/personal_workflows/cv_builder_skott.py",
        "fr",
        ("expérience", "compétence", "formation", "profil"),
        "output_only",
    ),
]


def _run_cli(script: str, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PY, script, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(WORKSPACE),
        timeout=60,
    )


def _extract_pdf_text(pdf_path: Path) -> str:
    """Read PDF -> text via pypdf for assertions."""
    from pypdf import PdfReader
    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _page_count(pdf_path: Path) -> int:
    from pypdf import PdfReader
    return len(PdfReader(str(pdf_path)).pages)


@pytest.mark.parametrize("script,lang,markers,cli_style", VARIANTS, ids=[v[0] for v in VARIANTS])
def test_variant_renders_pdf(tmp_path, script, lang, markers, cli_style):
    """Each cv_builder variant should produce a 2-page PDF with locale markers."""
    out_dir = WORKSPACE / ".tmp"
    out_dir.mkdir(exist_ok=True)

    if cli_style == "company_role":
        r = _run_cli(script, ["--company", "synthetic_test", "--role", "AI Product Manager"])
        pdf_glob = "cv_synthetic_test_debanjan_mazumdar*.pdf"
        pdf_path_explicit = None
    elif cli_style == "output_only":
        pdf_path_explicit = out_dir / "cv_synthetic_skott_test.pdf"
        r = _run_cli(script, ["--output", str(pdf_path_explicit)])
        pdf_glob = None
    else:
        raise AssertionError(f"unknown cli_style {cli_style!r}")
    assert r.returncode == 0, f"exit={r.returncode}\nstderr={r.stderr[-400:]}"

    # Locate the produced PDF.
    if pdf_path_explicit is not None:
        assert pdf_path_explicit.exists(), f"PDF not produced at {pdf_path_explicit}"
        pdf_path = pdf_path_explicit
    else:
        candidates = sorted(out_dir.glob(pdf_glob))
        assert candidates, f"no PDF matching {pdf_glob} under {out_dir}; stderr={r.stderr[-200:]}"
        pdf_path = candidates[-1]

    # Size sanity: non-trivial PDFs are >10 KB.
    size_kb = pdf_path.stat().st_size / 1024
    assert size_kb > 10, f"{pdf_path.name} is {size_kb:.1f} KB — too small to be a real CV"

    # Page count is a hard operator requirement: exactly 2 pages.
    assert _page_count(pdf_path) == 2, f"{pdf_path.name} has {_page_count(pdf_path)} pages, expected 2"

    # Locale + identity markers must appear in extracted text.
    text = _extract_pdf_text(pdf_path)
    text_lower = text.lower()
    assert "debanjan" in text_lower, "operator name missing from PDF"
    assert any(m.lower() in text_lower for m in markers), (
        f"none of the {lang} locale markers {markers} appear in {pdf_path.name}"
    )


def test_cv_builder_help_does_not_render(tmp_path):
    """`--help` should print and exit without writing a PDF."""
    r = _run_cli("execution/personal_workflows/cv_builder.py", ["--help"])
    assert r.returncode == 0
    assert "--company" in r.stdout

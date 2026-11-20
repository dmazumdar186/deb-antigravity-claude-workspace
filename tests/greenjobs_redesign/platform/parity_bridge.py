"""Parity bridge: what build_site.py renders and computes for the fixture, as JSON for the node tests.

description: Normalises the redesign's _fixture.json with build_site.normalise() for both editions
  (three jobs get an explicit apply mode: email, link, email), renders each edition with
  build_site.build_edition() into a scratch dir under the repo's .tmp/, and prints one JSON object:
  per site the D1 rows that represent the same jobs (jobs + employers + job_facets, facets taken from
  the Python classifier exactly as an import would write them), the static HTML of three job pages and
  the jobs list, and the figures build_site.py prints (salary_stats, sector tiles, regions,
  dashboard_kpis). tests/greenjobs_redesign/platform/parity.test.mjs seeds a FakeD1 with the rows,
  renders through the Worker and compares.
inputs: none (reads deliverables/greenjobs_redesign_2026-09-22/src read-only)
outputs: JSON on stdout; scratch pages under .tmp/parity_bridge/ (deleted and rewritten each run)
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(
    0, str(REPO / "execution" / "gtm_client_workflows" / "greenjobs_redesign")
)
import build_site as b  # noqa: E402

SRC = REPO / "deliverables" / "greenjobs_redesign_2026-09-22" / "src"
FIXTURE = SRC / "data" / "_fixture.json"
OUT = REPO / ".tmp" / "parity_bridge"
SITE_BASE = "https://parity.greenjobs.test/"
APPLY = {
    "1001": {"apply_mode": "email"},
    "1003": {
        "apply_mode": "link",
        "apply_url": "https://ats.example.com/jobs/1003?src=gj",
    },
    "1005": {"apply_mode": "email"},
}
PAGE_IDS = ["1001", "1003", "1005"]
# Employer-HTML shapes the sanitiser must handle identically in Python and in the Worker port.
SANITISE_SAMPLES = [
    "<p>Lead ecological surveys.</p><ul><li>Bat surveys</li><li>EIAR chapters</li></ul>",
    "<div>Location: Remote</div><div>Hours: 37.5 per week</div><div>Salary: €40k</div><div>We are a growing consultancy with a long track record.</div>",
    "<p><strong>The Role</strong></p><p>You will manage onshore wind projects across Munster and Leinster.</p>",
    "<p>* Grid connections<br>* Planning consents<br>* Stakeholder work</p>",
    '<h1>About us</h1><p>See <a href="/about" onclick="x()">our site</a> or <a href="mailto:jobs@example.com">email</a>.</p>',
    '<p style="color:red" class="x">Styled <span>text</span></p><p>&nbsp;</p><p><br><br></p><table><tr><td>A</td></tr></table>',
    "<p>Hello</p><script>alert(1)</script><style>p{}</style><iframe src=x></iframe>",
    '<p><img src=x onerror=alert(1)>Body</p><a href="javascript:alert(1)">bad</a><a href=" data:text/html,x">bad2</a>',
    "<p>&bull; One</p><p>&bull; Two</p><p>Then a sentence that is long enough to be body copy.</p>",
]


def rows_for(ed: str, data: dict, raw_by_id: dict) -> list[dict]:
    out = []
    for j in data["jobs"]:
        raw = raw_by_id[j["id"]]
        desc = str(raw.get("description_html") or "")
        out.append(
            {
                "id": f"{ed}:strat:{j['id']}",
                "employer_id": f"{ed}:strat:emp-{b.slugify(j['employer'])}",
                "employer": j["employer"],
                "title": j["title"],
                "location": j["location"],
                "region": (j["regions"] or [""])[0],
                "job_type": j["type"] or None,
                "sal_min": j["sal_min"],
                "sal_max": j["sal_max"],
                "currency": j["cur"] if j["cur"] in ("EUR", "GBP") else None,
                "period": j["period"],
                "sal_text": j["sal_text"] or None,
                "summary": j["summary"],
                "description": desc if len(desc) >= 20 else j["summary"],
                "apply_mode": (
                    j["apply_mode"] if j["apply_mode"] in ("email", "link") else "email"
                ),
                "apply_url": j["apply_url"] or None,
                "posted_at": f"{j['posted']}T09:00:00Z" if j["posted"] else None,
                "closing_at": f"{j['closing']}T23:59:59Z" if j["closing"] else None,
                "facets": {
                    "sectors": j["sectors"],
                    "regions": j["regions"],
                    "job_type": j["type"] or None,
                    "workplace": j["workplace"],
                    "contract": j["contract"],
                    "loc_class": j["loc_class"],
                    "level": j["level"],
                    "is_agency": int(bool(j["agency"])),
                    "salary_display": b.salary_label(j, b.EDITIONS[ed]["currency"])
                    or None,
                    "unverified_cur": int(b.is_unverified(j)),
                    "search_text": j["text"],
                },
            }
        )
    return out


def main() -> int:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for j in raw["jobs"]:
        j.update(APPLY.get(str(j["id"]), {"apply_mode": "email"}))  # no legacy Strategies link: every job is email or link
    raw_by_id = {str(j["id"]): j for j in raw["jobs"]}
    today = date.fromisoformat(raw["fetched"][:10])
    tpl = b.load_templates(SRC)
    brief = b.read_brief(SRC)
    logos = SRC / "assets" / "logos"
    for key, name in (
        ("bcorp_size", "b-corp-logo.svg"),
        ("onepct_size", "1fortheplanet.svg"),
    ):
        if (logos / name).is_file():
            brief[key] = b.image_size(logos / name)
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    result: dict = {"today": today.isoformat(), "sites": {}}
    for ed in ("ie", "uk"):
        data = b.normalise(raw, ed, SRC, logos, today)
        b.build_edition(data, SRC, OUT, tpl, brief, SITE_BASE, today, {})
        ed_meta = b.EDITIONS[ed]
        stats = b.salary_stats(data["jobs"], ed_meta)
        stats.pop("disclosed")
        sectors = [
            {
                **s,
                "stat": (
                    b.sector_stat(
                        [j for j in data["jobs"] if s["name"] in j["sectors"]],
                        ed_meta["sym"],
                    )
                    if s["n"]
                    else ""
                ),
            }
            for s in data["sectors"]
        ]
        pages = {
            jid: (OUT / ed / "jobs" / jid / "index.html").read_text(encoding="utf-8")
            for jid in (PAGE_IDS if ed == "ie" else [j["id"] for j in data["jobs"][:3]])
            if (OUT / ed / "jobs" / jid / "index.html").exists()
        }
        result["sites"][ed] = {
            "rows": rows_for(ed, data, raw_by_id),
            "pages": pages,
            "list_html": (OUT / ed / "jobs" / "index.html").read_text(encoding="utf-8"),
            "dashboard_html": (OUT / ed / "dashboard" / "index.html").read_text(encoding="utf-8"),
            "stats": {
                "salary": stats,
                "sectors": sectors,
                "regions": data["regions"],
                "kpis": b.dashboard_kpis(data),
            },
            "levels": {
                t: b.level_of(t)
                for t in [
                    "Senior Ecologist",
                    "Assistant Project Manager",
                    "Graduate Engineer",
                    "Head of ESG",
                    "Lead-free Solder Tech",
                    "Ecologist",
                ]
            },
            "agency": {
                n: b.is_agency(n)
                for n in [
                    "Gaia Talent",
                    "Acme Recruitment Ltd",
                    "Sunrise Energy",
                    "Search & Selection Partners",
                ]
            },
            "labels": [
                {"in": x, "out": b.salary_label(x, ed_meta["currency"])}
                for x in [
                    {
                        "sal_min": 55000,
                        "sal_max": 65000,
                        "cur": "EUR",
                        "period": "year",
                        "sal_text": "",
                    },
                    {
                        "sal_min": 30000,
                        "sal_max": None,
                        "cur": "GBP",
                        "period": "year",
                        "sal_text": "up to £30k",
                    },
                    {
                        "sal_min": 18.5,
                        "sal_max": 22,
                        "cur": "EUR",
                        "period": "hour",
                        "sal_text": "",
                    },
                    {
                        "sal_min": 62500,
                        "sal_max": 62500,
                        "cur": "GBP",
                        "period": "year",
                        "sal_text": "",
                    },
                    {
                        "sal_min": 450,
                        "sal_max": 550,
                        "cur": "EUR",
                        "period": "day",
                        "sal_text": "",
                    },
                ]
            ],
        }
    base = "https://www.greenjobs.ie/jobs/x/"
    result["sanitise"] = [
        {"in": s, "out": b.sanitise_html(s, base)} for s in SANITISE_SAMPLES
    ]
    json.dump(result, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())

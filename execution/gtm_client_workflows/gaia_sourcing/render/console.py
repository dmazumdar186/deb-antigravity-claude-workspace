"""
L14 -- the operator console.

A static site generator, same shape as render.py's dossier but for the
Gaia-side consultant rather than the client: `deliverables/<campaign_id>/console/`
with pages for what needs action today, the two job roles, a live shortlist
per role, one detail card per candidate, the pool map and the scorecard.

Two rules carried over from render.py, because they matter here too:

  Never invent data. A stage file that has not run yet (outreach_queue.json,
  replies.json, health.json, scorecard.json -- all owned by other in-flight
  workstreams per RADAR_CONTRACTS.md section E/F) renders an explicit empty
  state, never a guess and never a silent zero dressed up as a real count.

  Every claim on a card carries its verbatim quote and a link to the source
  document -- reused directly from render.render rather than re-implemented,
  because a second escaping/repair path is a second place for the mojibake
  and injection bugs render.py already paid to fix.

Entry point: `render_console(campaign_id, out_dir, run_dir=None, page_status=None)`.
`run_dir` defaults to `run/<campaign_id>/` and exists as a parameter only so
tests can point it at a fixture directory without touching a real run.
`--stage console` wiring into run.py is NOT done here (run.py is owned by
other workstreams this session) -- see the module docstring's closing note.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

from ..core.config import CONFIG, PKG_ROOT, WORKSPACE_ROOT, secret
from ..roles import ROLE1, ROLE2, ROLES
from .render import DIM_LABEL, TIER_LABEL, _safe_url, _short_url, e, repair

# Configured once, read-only here. Empty means "no live endpoint" -- every
# page that would otherwise POST to it degrades to a static, honest note
# instead of a dead button. Never required: the console is useful with zero
# Modal infrastructure, just not "live".
MODAL_RADAR_URL = secret("MODAL_RADAR_URL", required=False)

PAGES = ("index", "jobs", "shortlist", "card", "poolmap", "scorecard")


def _default_page_status() -> dict:
    return {p: "CACHED" for p in PAGES}


# ---------------------------------------------------------------------------
# Loading. Never raises -- a missing/unreadable stage file is a fact this
# console reports, not an exception that stops it rendering everything else.
# ---------------------------------------------------------------------------


def _load_json(run_dir: Path, name: str):
    p = run_dir / (name + ".json")
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        # A torn or unreadable stage file must not take the whole console
        # down with it -- every other page still has something to say.
        print("console: could not read " + str(p) + ": " + repr(exc))
        return None


class RunSnapshot:
    """Everything the console reads, loaded once and handed to every page."""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        extract = _load_json(run_dir, "extract") or {}
        self.persons: dict = extract.get("persons", {}) or {}
        validate = _load_json(run_dir, "validate") or {}
        self.claims: list = validate.get("claims", []) or []
        self.by_person: dict[str, list] = {}
        for c in self.claims:
            pid = c.get("subject_person_id")
            if pid:
                self.by_person.setdefault(pid, []).append(c)
        self.gate: dict = _load_json(run_dir, "gate") or {}
        self.contact: dict = _load_json(run_dir, "contact") or {}
        self.movability: dict = _load_json(run_dir, "movability") or {}
        self.messages: dict = _load_json(run_dir, "messages") or {}
        self.poolmap: dict = _load_json(run_dir, "poolmap") or {}
        self.adversarial: dict = _load_json(run_dir, "adversarial") or {}

        # Optional, owned by other in-flight workstreams. Absence is a normal
        # state this console must show honestly, never paper over.
        self.health = _load_json(run_dir, "health")
        self.outreach_queue = _load_json(run_dir, "outreach_queue")
        self.replies = _load_json(run_dir, "replies")
        self.scorecard = _load_json(run_dir, "scorecard")

    def persons_for_role(self, role_id: str) -> list[str]:
        return [pid for pid, g in self.gate.items() if g.get("role_id") == role_id]


# ---------------------------------------------------------------------------
# Shared chrome
# ---------------------------------------------------------------------------

CSS = """
:root{
  --ground:#F4F6F3; --surface:#FFFFFF; --ink:#1A2321; --muted:#5B6763; --line:#D6DDD8;
  --accent:#2E6B4F; --accent-tint:#E4EFE9;
  --warn:#B4791C; --warn-tint:#FBF0DF;
  --fail:#A9432F; --fail-tint:#F8E6E1;
  --focus:#2E6B4F;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --ground:#121A17; --surface:#1A2420; --ink:#E8EEEA; --muted:#98A59F; --line:#2C3934;
    --accent:#6FBF95; --accent-tint:#1D2C25;
    --warn:#E0A84B; --warn-tint:#2B2517;
    --fail:#E27A66; --fail-tint:#2E1E1A;
    --focus:#6FBF95;
  }
}
:root[data-theme="dark"]{
  --ground:#121A17; --surface:#1A2420; --ink:#E8EEEA; --muted:#98A59F; --line:#2C3934;
  --accent:#6FBF95; --accent-tint:#1D2C25;
  --warn:#E0A84B; --warn-tint:#2B2517;
  --fail:#E27A66; --fail-tint:#2E1E1A;
  --focus:#6FBF95;
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--ground); color:var(--ink);
  font:15px/1.5 "IBM Plex Sans","Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  -webkit-text-size-adjust:100%;
}
h1,h2,h3{font-family:"Bricolage Grotesque",Georgia,serif; text-wrap:balance; margin:0}
.mono,.num,code,.quote,.chip,.pill{font-family:"IBM Plex Mono","SFMono-Regular",Consolas,monospace}
.label{text-transform:uppercase; letter-spacing:.06em; font-size:11px; color:var(--muted); font-weight:600}
a{color:var(--accent)}
button{font:inherit}
:focus-visible{outline:2.5px solid var(--focus); outline-offset:2px}
@media (prefers-reduced-motion:reduce){*{transition:none!important; animation:none!important}}

.page{max-width:1200px; margin:0 auto; padding:20px 16px 64px}
header.top{border-bottom:2px solid var(--accent); padding-bottom:14px; margin-bottom:18px}
header.top h1{font-size:24px; font-weight:700; display:flex; align-items:center; gap:10px; flex-wrap:wrap}
header.top .lede{color:var(--muted); margin-top:6px; font-size:14px}
nav.tabs{display:flex; flex-wrap:wrap; gap:6px; margin-top:12px}
nav.tabs a{
  display:inline-block; border:1px solid var(--line); border-radius:6px; padding:5px 10px;
  font-size:12.5px; text-decoration:none; color:var(--ink); background:var(--surface);
}
nav.tabs a.on{border-color:var(--accent); background:var(--accent-tint); color:var(--accent); font-weight:600}

.badge{display:inline-block; font-size:10.5px; font-weight:700; letter-spacing:.05em; border-radius:4px; padding:1px 7px; text-transform:uppercase}
.badge.LIVE{background:var(--accent-tint); color:var(--accent)}
.badge.CACHED{background:var(--line); color:var(--muted)}
.badge.STUB{background:var(--warn-tint); color:var(--warn)}

.health{background:var(--surface); border:1px solid var(--line); border-left:4px solid var(--accent); border-radius:8px; padding:9px 13px; font-size:13px; margin:14px 0}
.health.stale{border-left-color:var(--warn); color:var(--warn)}
.empty{color:var(--muted); font-style:italic; font-size:13.5px; padding:14px; border:1px dashed var(--line); border-radius:8px; background:var(--surface)}

.tiles{display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:10px; margin:14px 0}
.tile{background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:12px 14px}
.tile .tnum{font-size:24px; font-weight:600}
.tile .tlabel{font-size:11.5px; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; margin-top:2px}

section.block{margin:26px 0}
section.block h2{font-size:18px; margin-bottom:8px}
section.block .sub{color:var(--muted); font-size:12.5px; margin-bottom:10px}

.tbl-wrap{overflow-x:auto; border:1px solid var(--line); border-radius:10px; background:var(--surface)}
table.tb{width:100%; border-collapse:collapse; min-width:640px; font-size:13px}
table.tb th{text-align:left; font-size:11px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); font-weight:600; padding:9px 10px; border-bottom:2px solid var(--accent)}
table.tb td{padding:9px 10px; border-bottom:1px solid var(--line); vertical-align:top}
tr.excluded{opacity:.55}
.nm{font-weight:600}
.ro{color:var(--muted); font-size:12px}

.pill{display:inline-block; font-size:11px; font-weight:700; border-radius:20px; padding:2px 9px}
.pill.A,.pill.stays{background:var(--accent-tint); color:var(--accent)}
.pill.B{background:var(--warn-tint); color:var(--warn)}
.pill.C{background:var(--line); color:var(--muted)}
.pill.EXCLUDED,.pill.excluded{background:var(--fail-tint); color:var(--fail)}
.chip{display:inline-block; font-size:11px; border-radius:4px; padding:1.5px 6px; margin:1px 3px 1px 0; border:1px solid var(--line); color:var(--muted)}
.chip.fail{background:var(--fail-tint); color:var(--fail); border-color:transparent}
.chip.pass{background:var(--accent-tint); color:var(--accent); border-color:transparent}

.claim{margin:0 0 10px; padding-left:11px; border-left:3px solid var(--line)}
.claim blockquote{margin:0; padding:0; border:0; color:var(--ink); display:inline; font-style:italic}
.claim .dim{font-size:10.5px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); display:block; margin-bottom:2px}
.claim .src{font-size:11.5px; color:var(--muted); display:block; margin-top:3px}

.rail{background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:14px 16px; margin:14px 0}
.rail .field{margin-bottom:8px; font-size:13px}
.rail label{display:block; margin-bottom:3px; font-size:11.5px; color:var(--muted)}
.rail input,.rail select{padding:5px 7px; border:1px solid var(--line); border-radius:5px; background:var(--ground); color:var(--ink); font-size:13px}
.btn{border:1px solid var(--line); background:var(--surface); color:var(--ink); border-radius:7px; padding:8px 12px; font-size:13px; font-weight:600; cursor:pointer}
.btn.primary{background:var(--accent); border-color:var(--accent); color:#fff}
.btn.reject{background:var(--fail); border-color:var(--fail); color:#fff}
.btn:disabled{opacity:.5; cursor:not-allowed}
.note{color:var(--muted); font-size:11.5px; margin-top:6px; line-height:1.4}
.msg-box{white-space:pre-wrap; background:var(--ground); border:1px solid var(--line); border-radius:6px; padding:8px 10px; font-size:13px; margin:4px 0 10px}
.kv{display:grid; grid-template-columns:140px 1fr; gap:4px 10px; font-size:13px; margin-bottom:10px}
.kv .k{color:var(--muted); font-size:11.5px; text-transform:uppercase; letter-spacing:.05em}
footer.bottom{margin-top:36px; padding-top:14px; border-top:1px solid var(--line); font-size:11.5px; color:var(--muted)}
"""


def _nav(active: str, campaign_id: str, role_links: list[tuple[str, str]]) -> str:
    items = [("index.html", "Today", "index"), ("jobs.html", "Jobs", "jobs")]
    items += [(href, label, "shortlist") for href, label in role_links]
    items += [("poolmap.html", "Pool map", "poolmap"), ("scorecard.html", "Scorecard", "scorecard")]
    # Shortlist tabs are only marked "on" for the exact role page being
    # rendered -- the caller passes a role_links list pre-filtered to that
    # one role whenever active=="shortlist", so any href match is the match.
    out = ['<nav class="tabs">']
    for href, label, key in items:
        on = key == active
        out.append('<a class="' + ("on" if on else "") + '" href="'
                   + e(href) + '">' + e(label) + "</a>")
    out.append("</nav>")
    return "".join(out)


def _health_banner(health: Optional[dict]) -> str:
    if not health:
        return ""
    days = health.get("days_since_refresh")
    if days is None and health.get("pool_refreshed_at"):
        try:
            refreshed = date.fromisoformat(str(health["pool_refreshed_at"])[:10])
            days = (date.today() - refreshed).days
        except ValueError:
            days = None
    if days is None:
        # health.json exists but not in a shape this console recognises --
        # showing a banner built from a field we cannot parse would be a
        # kind of invention this file exists to avoid, so it is skipped
        # rather than guessed at.
        return ""
    stale = bool(health.get("stale")) or days > 7
    return (
        '<div class="health' + (" stale" if stale else "") + '">'
        "Pool last refreshed " + str(days) + " day" + ("" if days == 1 else "s")
        + " ago." + (" Consider a re-harvest." if stale else "") + "</div>"
    )


def _badge(page_key: str, page_status: dict) -> str:
    status = page_status.get(page_key, "CACHED")
    return '<span class="badge ' + e(status) + '">' + e(status) + "</span>"


def _shell(
    title: str, active: str, page_key: str, page_status: dict,
    campaign_id: str, health: Optional[dict], role_links: list[tuple[str, str]],
    body: str,
) -> str:
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta name='robots' content='noindex,nofollow'>"
        "<link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>"
        "<link href='https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:"
        "wght@600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:"
        "wght@400;500&display=swap' rel='stylesheet'>"
        "<title>" + e(title) + " -- Gaia Console</title>"
        "<style>" + CSS + "</style></head><body><div class='page'>"
        "<header class='top'><h1>" + e(title) + " " + _badge(page_key, page_status)
        + "</h1><p class='lede'>Campaign " + e(campaign_id)
        + " &middot; operator console, not for client distribution</p>"
        + _health_banner(health)
        + _nav(active, campaign_id, role_links)
        + "</header>" + body
        + "<footer class='bottom'>Generated " + date.today().isoformat()
        + " &middot; static console, rebuilt from run/" + e(campaign_id)
        + "/*.json &middot; missing stage files render as empty states, "
        "never as guesses.</footer></div></body></html>"
    )


def _role_links() -> list[tuple[str, str]]:
    return [
        ("shortlist_" + ROLE1.role_id + ".html", ROLE1.title),
        ("shortlist_" + ROLE2.role_id + ".html", ROLE2.title),
    ]


# ---------------------------------------------------------------------------
# Evidence rendering -- thin wrapper over render.py's own claim conventions
# (escaping via e(), the same DIM_LABEL vocabulary) rather than a parallel
# implementation.
# ---------------------------------------------------------------------------


def _claims_block(claims: list[dict], limit: int = 6) -> str:
    if not claims:
        return '<p class="empty">No validated evidence on file for this person.</p>'
    out = []
    for c in claims[:limit]:
        dim = DIM_LABEL.get(c.get("dimension"), c.get("dimension", "?"))
        src = c.get("source_url") or ""
        out.append(
            '<div class="claim"><span class="dim">' + e(dim) + "</span>"
            "<blockquote>&ldquo;" + e(str(c.get("evidence_quote", "")).strip())
            + "&rdquo;</blockquote>"
            '<span class="src">' + e(c.get("assertion", "")) + " &middot; "
            + ('<a href="' + e(_safe_url(src)) + '">' + e(_short_url(src)) + "</a>"
               if _safe_url(src) else "source not recorded")
            + "</span></div>"
        )
    if len(claims) > limit:
        out.append('<p class="note">Showing ' + str(limit) + " of " + str(len(claims))
                   + " validated claims; the rest are in validate.json.</p>")
    return "".join(out)


# ---------------------------------------------------------------------------
# index.html -- Today
# ---------------------------------------------------------------------------


def render_index(snap: RunSnapshot, campaign_id: str, page_status: dict) -> str:
    body = []

    # Pending approvals. Shape assumed pending layers/outreach_queue.py
    # (RADAR_CONTRACTS.md section E): a dict or list of draft records each
    # carrying person_id/status; only "pending_approval" surfaces here.
    body.append('<section class="block"><h2>Pending approvals</h2>')
    body.append('<p class="sub">Drafts waiting on a consultant\'s go/no-go.</p>')
    queue = snap.outreach_queue
    if queue is None:
        body.append(
            '<p class="empty">No outreach_queue.json yet for this campaign -- '
            "the approval queue has not run. Nothing is pending because "
            "nothing has been checked, not because everything is clear.</p>"
        )
    else:
        rows = list(queue.values()) if isinstance(queue, dict) else list(queue)
        pending = [r for r in rows if isinstance(r, dict)
                   and r.get("status") == "pending_approval"]
        if not pending:
            body.append('<p class="empty">Queue is present and empty -- nothing '
                        "is waiting on approval right now.</p>")
        else:
            body.append('<div class="tbl-wrap"><table class="tb"><thead><tr>'
                        "<th>Person</th><th>Role</th><th>Draft</th></tr></thead><tbody>")
            for r in pending:
                pid = r.get("person_id", "?")
                person = snap.persons.get(pid, {})
                body.append(
                    "<tr><td><a href='card_" + e(pid) + ".html'>"
                    + e(person.get("full_name", pid)) + "</a></td>"
                    "<td>" + e(r.get("role_id", "")) + "</td>"
                    "<td>" + e(r.get("draft_id", r.get("channel", "-"))) + "</td></tr>"
                )
            body.append("</tbody></table></div>")
    body.append("</section>")

    # New movable-now. No baseline exists to diff "new" against in this
    # static generator, so it is named honestly as "currently high-movability"
    # rather than claiming a delta this file has no way to compute.
    body.append('<section class="block"><h2>Movable now</h2>')
    body.append('<p class="sub">Delivered candidates flagged high movability. '
               "No prior snapshot to diff against yet, so this is the current "
               "list, not a delta.</p>")
    movable = [
        (pid, snap.movability[pid]) for pid in snap.movability
        if snap.movability[pid].get("assessment") == "high" and pid in snap.gate
    ]
    if not movable:
        body.append('<p class="empty">No delivered candidate is currently '
                    "flagged high movability.</p>")
    else:
        body.append('<div class="tbl-wrap"><table class="tb"><thead><tr>'
                    "<th>Person</th><th>Role</th><th>Why</th></tr></thead><tbody>")
        for pid, mov in movable:
            person = snap.persons.get(pid, {})
            g = snap.gate.get(pid, {})
            body.append(
                "<tr><td><a href='card_" + e(pid) + ".html'>"
                + e(person.get("full_name", pid)) + "</a></td>"
                "<td>" + e(ROLES.get(g.get("role_id"), g.get("role_id", "?")).title
                          if g.get("role_id") in ROLES else g.get("role_id", "?")) + "</td>"
                "<td>" + e(mov.get("rationale", "")) + "</td></tr>"
            )
        body.append("</tbody></table></div>")
    body.append("</section>")

    # Replies needing action. Shape assumed per RADAR_CONTRACTS.md section F
    # ReplyVerdict-like records; only genuinely actionable next_actions
    # surface (consultant_answers / human_review / book_call).
    body.append('<section class="block"><h2>Replies needing action</h2>')
    body.append('<p class="sub">Candidate replies whose classification asked '
               "for a human.</p>")
    replies = snap.replies
    if replies is None:
        body.append('<p class="empty">No replies.json yet for this campaign -- '
                    "reply classification has not produced anything to show.</p>")
    else:
        rows = list(replies.values()) if isinstance(replies, dict) else list(replies)
        actionable = [
            r for r in rows if isinstance(r, dict)
            and r.get("next_action") in ("consultant_answers", "human_review", "book_call")
        ]
        if not actionable:
            body.append('<p class="empty">Replies are logged; none need a '
                        "human right now.</p>")
        else:
            body.append('<div class="tbl-wrap"><table class="tb"><thead><tr>'
                        "<th>Person</th><th>Label</th><th>Action</th><th>Evidence</th>"
                        "</tr></thead><tbody>")
            for r in actionable:
                pid = r.get("person_id", "?")
                person = snap.persons.get(pid, {})
                body.append(
                    "<tr><td>" + (
                        "<a href='card_" + e(pid) + ".html'>" + e(person.get("full_name", pid)) + "</a>"
                        if pid in snap.persons else e(pid)
                    ) + "</td>"
                    "<td>" + e(r.get("label", "")) + "</td>"
                    "<td>" + e(r.get("next_action", "")) + "</td>"
                    "<td>" + e(r.get("evidence", "")) + "</td></tr>"
                )
            body.append("</tbody></table></div>")
    body.append("</section>")

    return "".join(body)


# ---------------------------------------------------------------------------
# jobs.html
# ---------------------------------------------------------------------------


def render_jobs(snap: RunSnapshot, campaign_id: str, page_status: dict) -> str:
    body = ['<section class="block"><h2>Roles</h2><div class="tiles">']
    for spec in (ROLE1, ROLE2):
        pids = snap.persons_for_role(spec.role_id)
        counts = {"A": 0, "B": 0, "C": 0, "EXCLUDED": 0}
        for pid in pids:
            counts[snap.gate[pid].get("tier", "EXCLUDED")] = (
                counts.get(snap.gate[pid].get("tier", "EXCLUDED"), 0) + 1
            )
        m = snap.poolmap.get(spec.role_id, {})
        body.append(
            '<div class="tile"><div class="tnum">' + str(m.get("delivered", 0))
            + " / " + str(spec.target_count) + "</div>"
            '<div class="tlabel">' + e(spec.title) + "</div>"
            '<p class="note">A=' + str(counts["A"]) + " B=" + str(counts["B"])
            + " C=" + str(counts["C"]) + " excluded=" + str(counts["EXCLUDED"])
            + "</p><p class='note'><a href='shortlist_" + e(spec.role_id)
            + ".html'>Open shortlist &rarr;</a></p></div>"
        )
    body.append("</div></section>")
    return "".join(body)


# ---------------------------------------------------------------------------
# shortlist_<role>.html
# ---------------------------------------------------------------------------


def _brief_rail(spec) -> str:
    params_by_check = {g.check: g.params for g in spec.hard_gates}
    ceiling = params_by_check.get("seniority_ceiling", {})
    floor = params_by_check.get("seniority_years", {})
    loc = params_by_check.get("located_ie", {})
    disc = params_by_check.get("discipline", {})

    modal_note = (
        "Live re-cut endpoint configured. Submitting posts to "
        + e(MODAL_RADAR_URL) + "/recut and shows the result below, without "
        "touching any cached stage file."
        if MODAL_RADAR_URL else
        "No MODAL_RADAR_URL configured for this build -- this panel shows "
        "the brief's current defaults only. Deploy execution/modal_radar.py "
        "and set MODAL_RADAR_URL to enable a live re-cut from this page."
    )

    return (
        '<div class="rail" id="brief-rail" data-role-id="' + e(spec.role_id) + '" '
        'data-modal-url="' + e(MODAL_RADAR_URL) + '">'
        "<h3>Brief controls</h3>"
        '<p class="note">Defaults below come straight from roles.py for this role.</p>'
        '<div class="field"><label>Max grade (seniority ceiling)</label>'
        '<select id="rc-max-grade"><option value="">no ceiling</option>'
        + "".join(
            "<option value='" + e(g) + "'"
            + (" selected" if ceiling.get("max_grade") == g else "") + ">" + e(g) + "</option>"
            for g in ("senior_engineer", "principal_or_associate", "associate_director", "director")
        )
        + "</select></div>"
        '<div class="field"><label>Max years</label>'
        '<input type="number" id="rc-max-years" value="'
        + e(ceiling.get("max_years", "")) + '"></div>'
        '<div class="field"><label>Min years</label>'
        '<input type="number" id="rc-min-years" value="'
        + e(floor.get("min_years", "")) + '"></div>'
        '<div class="field"><label>Counties (comma-separated, blank = any ROI)</label>'
        '<input type="text" id="rc-counties" value="'
        + e(", ".join(loc.get("counties", []))) + '"></div>'
        '<div class="field"><label><input type="checkbox" id="rc-strict"'
        + (" checked" if loc.get("require_direct_evidence") else "")
        + "> Strict location (direct residence evidence only)</label></div>"
        '<p class="note">Discipline include-terms (fixed, not editable here): '
        + e(", ".join(disc.get("include", [])[:6])) + "</p>"
        '<button class="btn primary" id="rc-run" type="button"'
        + ("" if MODAL_RADAR_URL else " disabled") + ">Re-cut live</button>"
        '<p class="note" id="rc-note">' + e(modal_note) + "</p>"
        '<pre class="msg-box" id="rc-result" hidden></pre>'
        "</div>"
        "<script>(function(){"
        "var rail=document.getElementById('brief-rail'); if(!rail) return;"
        "var url=rail.getAttribute('data-modal-url'); var role=rail.getAttribute('data-role-id');"
        "var btn=document.getElementById('rc-run'); if(!btn||!url) return;"
        "btn.addEventListener('click', function(){"
        "  var counties=(document.getElementById('rc-counties').value||'')"
        "    .split(',').map(function(s){return s.trim();}).filter(Boolean);"
        "  var body={campaign_id:document.body.getAttribute('data-campaign'), role_id:role,"
        "    brief_overrides:{"
        "      max_grade: document.getElementById('rc-max-grade').value || null,"
        "      max_years: document.getElementById('rc-max-years').value ? "
        "        parseInt(document.getElementById('rc-max-years').value,10) : null,"
        "      min_years: document.getElementById('rc-min-years').value ? "
        "        parseInt(document.getElementById('rc-min-years').value,10) : null,"
        "      counties: counties,"
        "      strict_location: document.getElementById('rc-strict').checked"
        "    }};"
        "  var out=document.getElementById('rc-result'); out.hidden=false;"
        "  out.textContent='Running...';"
        "  fetch(url + '/recut', {method:'POST', headers:{'Content-Type':'application/json'},"
        "    body: JSON.stringify(body)})"
        "    .then(function(r){return r.json();})"
        "    .then(function(j){out.textContent=JSON.stringify(j, null, 1);})"
        "    .catch(function(err){out.textContent='Request failed: ' + err;});"
        "});"
        "})();</script>"
    )


def render_shortlist(snap: RunSnapshot, spec, campaign_id: str, page_status: dict) -> str:
    pids = snap.persons_for_role(spec.role_id)
    rows_order = {"A": 0, "B": 1, "C": 2, "EXCLUDED": 3}
    pids.sort(key=lambda p: (
        rows_order.get(snap.gate.get(p, {}).get("tier", "EXCLUDED"), 4),
        -(snap.gate.get(p, {}).get("n_claims", 0)),
        p,
    ))

    body = ['<section class="block"><h2>' + e(spec.title) + " shortlist</h2>"]
    body.append(_brief_rail(spec))

    if not pids:
        body.append('<p class="empty">No candidates on file for this role yet.</p></section>')
        return "".join(body)

    body.append('<div class="tbl-wrap"><table class="tb"><thead><tr>'
               "<th>Candidate</th><th>Tier</th><th>Failed gates</th>"
               "<th>Contact</th><th>Movability</th><th></th></tr></thead><tbody>")
    for pid in pids:
        g = snap.gate.get(pid, {})
        person = snap.persons.get(pid, {})
        tier = g.get("tier", "EXCLUDED")
        failed = [r.get("gate_id") for r in g.get("gates", []) if not r.get("passed")]
        contact = snap.contact.get(pid, {})
        mov = snap.movability.get(pid, {})
        body.append(
            '<tr class="' + ("excluded" if tier == "EXCLUDED" else "") + '">'
            "<td><a href='card_" + e(pid) + ".html'><span class='nm'>"
            + e(person.get("full_name", pid)) + "</span></a>"
            "<div class='ro'>" + e(person.get("current_title") or "title not stated")
            + (" &middot; " + e(person["current_employer"]) if person.get("current_employer") else "")
            + "</div></td>"
            "<td><span class='pill " + e(tier) + "'>" + e(tier) + "</span></td>"
            "<td>" + ("".join("<span class='chip fail'>" + e(f) + "</span>" for f in failed)
                      or "<span class='chip pass'>none</span>") + "</td>"
            "<td><span class='chip'>" + e(contact.get("email_status", "none")) + "</span>"
            + (" <span class='chip'>linkedin</span>" if contact.get("linkedin_url") else "") + "</td>"
            "<td><span class='chip'>" + e(mov.get("assessment", "unknown")) + "</span></td>"
            "<td><a href='card_" + e(pid) + ".html'>Detail &rarr;</a></td>"
            "</tr>"
        )
    body.append("</tbody></table></div></section>")
    return "".join(body)


# ---------------------------------------------------------------------------
# card_<person>.html
# ---------------------------------------------------------------------------


def render_card(snap: RunSnapshot, pid: str, campaign_id: str, page_status: dict) -> str:
    person = snap.persons.get(pid, {})
    g = snap.gate.get(pid, {})
    contact = snap.contact.get(pid, {})
    mov = snap.movability.get(pid, {})
    outreach = snap.messages.get(pid)
    claims = snap.by_person.get(pid, [])
    spec = ROLES.get(g.get("role_id"))

    body = ['<section class="block">']
    body.append(
        "<h2>" + e(person.get("full_name", pid)) + "</h2>"
        '<p class="sub">' + e(person.get("current_title") or "title not stated")
        + (" &middot; " + e(person["current_employer"]) if person.get("current_employer") else "")
        + (" &middot; " + e(person["location"]) if person.get("location") else "")
        + "</p>"
    )

    body.append('<h3>Gate results -- ' + e(spec.title if spec else g.get("role_id", "?")) + "</h3>")
    if not g:
        body.append('<p class="empty">No gate.json entry for this person.</p>')
    else:
        body.append('<span class="pill ' + e(g.get("tier", "EXCLUDED")) + '">'
                    + e(g.get("tier", "EXCLUDED")) + "</span> "
                    + e(TIER_LABEL.get(g.get("tier", ""), "")))
        body.append('<div class="tbl-wrap" style="margin-top:8px"><table class="tb">'
                   "<thead><tr><th>Gate</th><th>Result</th><th>Note</th></tr></thead><tbody>")
        for r in g.get("gates", []):
            body.append(
                "<tr><td>" + e(r.get("gate_id", "")) + "</td>"
                "<td><span class='chip " + ("pass" if r.get("passed") else "fail") + "'>"
                + ("passed" if r.get("passed") else "failed") + "</span></td>"
                "<td>" + e(r.get("note") or "-") + "</td></tr>"
            )
        body.append("</tbody></table></div>")

    body.append('<h3>Evidence</h3>')
    body.append(_claims_block(claims, limit=10))

    body.append('<h3>Contact</h3><div class="kv">')
    body.append('<div class="k">Email</div><div>' + (e(contact.get("email")) if contact.get("email")
               else "<span class='empty' style='padding:0;border:0'>not found</span>")
               + " <span class='chip'>" + e(contact.get("email_status", "none")) + "</span></div>")
    body.append('<div class="k">LinkedIn</div><div>' + (
        "<a href='" + e(_safe_url(contact.get("linkedin_url") or "")) + "'>"
        + e(_short_url(contact.get("linkedin_url"))) + "</a>" if contact.get("linkedin_url")
        else "<span class='empty' style='padding:0;border:0'>not found</span>"
    ) + "</div>")
    body.append('<div class="k">First channel</div><div>'
               + e(contact.get("recommended_first_channel", "linkedin")) + "</div>")
    body.append("</div>")

    body.append('<h3>Movability</h3>')
    if mov:
        body.append(
            "<p><strong>" + e(mov.get("assessment", "unknown")) + "</strong> -- "
            + e(mov.get("rationale") or "no rationale recorded") + "</p>"
        )
    else:
        body.append('<p class="empty">No movability.json entry for this person.</p>')

    body.append('<h3>Outreach draft</h3>')
    if not outreach:
        body.append('<p class="empty">No outreach drafted for this person yet.</p>')
    else:
        body.append('<p class="note">LinkedIn note</p><div class="msg-box">'
                   + e(outreach.get("linkedin_note", "")) + "</div>")
        body.append('<p class="note">Email &mdash; ' + e(outreach.get("email_subject", ""))
                   + '</p><div class="msg-box">' + e(outreach.get("email_body", "")) + "</div>")
        if outreach.get("follow_up"):
            body.append('<p class="note">Follow-up</p><div class="msg-box">'
                       + e(outreach["follow_up"]) + "</div>")

        draft_id = pid  # outreach_queue.py (section E) is the eventual owner
        # of real draft ids; until it lands the person_id is the only stable
        # handle this console has for "which draft got approved".
        body.append(
            '<div id="approve-box" data-draft-id="' + e(draft_id)
            + '" data-campaign="' + e(campaign_id) + '" data-modal-url="' + e(MODAL_RADAR_URL) + '">'
            '<button class="btn primary" id="btn-approve" type="button">Approve</button> '
            '<button class="btn reject" id="btn-reject" type="button">Reject</button>'
            '<p class="note" id="approve-note">'
            + (
                "Posts to " + e(MODAL_RADAR_URL) + "/approve and appends to "
                "run/" + e(campaign_id) + "/approvals.jsonl on the server."
                if MODAL_RADAR_URL else
                "No MODAL_RADAR_URL configured -- approval intent is recorded "
                "only in this browser (localStorage), not synced anywhere. "
                "Deploy execution/modal_radar.py and set MODAL_RADAR_URL for "
                "a real record."
            )
            + "</p></div>"
            "<script>(function(){"
            "var box=document.getElementById('approve-box'); if(!box) return;"
            "var url=box.getAttribute('data-modal-url'); var draftId=box.getAttribute('data-draft-id');"
            "var campaign=box.getAttribute('data-campaign');"
            "function act(action){"
            "  var note=document.getElementById('approve-note');"
            "  if(url){"
            "    fetch(url + '/approve', {method:'POST', headers:{'Content-Type':'application/json'},"
            "      body: JSON.stringify({campaign_id:campaign, draft_id:draftId, by:'console', action:action})})"
            "      .then(function(r){return r.json();})"
            "      .then(function(j){note.textContent='Recorded: ' + JSON.stringify(j);})"
            "      .catch(function(err){note.textContent='Request failed: ' + err;});"
            "  } else {"
            "    try {"
            "      var key='gaia_console_approvals_' + campaign;"
            "      var existing=JSON.parse(localStorage.getItem(key) || '[]');"
            "      existing.push({draft_id:draftId, action:action, at:new Date().toISOString()});"
            "      localStorage.setItem(key, JSON.stringify(existing));"
            "      note.textContent='Approval recorded locally in this browser only ('+action+').';"
            "    } catch(err) { note.textContent='Could not record locally: ' + err; }"
            "  }"
            "}"
            "document.getElementById('btn-approve').addEventListener('click', function(){act('approve');});"
            "document.getElementById('btn-reject').addEventListener('click', function(){act('reject');});"
            "})();</script>"
        )

    body.append("</section>")
    return "".join(body)


# ---------------------------------------------------------------------------
# poolmap.html
# ---------------------------------------------------------------------------


def render_poolmap(snap: RunSnapshot, campaign_id: str, page_status: dict) -> str:
    body = ['<section class="block"><h2>Pool map</h2>'
           '<p class="sub">The honest denominator, per role.</p>']
    if not snap.poolmap:
        body.append('<p class="empty">No poolmap.json for this campaign yet.</p></section>')
        return "".join(body)
    for spec in (ROLE1, ROLE2):
        m = snap.poolmap.get(spec.role_id)
        if not m:
            continue
        body.append("<h3>" + e(spec.title) + "</h3>")
        body.append('<div class="tiles">')
        for label, key in (
            ("Assessed", "profiles_assessed"), ("Raw claims", "raw_claims"),
            ("Validated", "evidence_validated"), ("Passed gates", "passed_all_gates"),
            ("Delivered", "delivered"),
        ):
            body.append('<div class="tile"><div class="tnum">' + str(m.get(key, 0))
                       + '</div><div class="tlabel">' + e(label) + "</div></div>")
        body.append("</div>")
        if m.get("exclusions"):
            body.append('<div class="tbl-wrap"><table class="tb"><thead><tr>'
                       "<th>Failed gate</th><th>Candidates</th></tr></thead><tbody>")
            for row in m["exclusions"]:
                body.append("<tr><td>" + e(row.get("reason", "")) + "</td><td>"
                           + str(row.get("count", 0)) + "</td></tr>")
            body.append("</tbody></table></div>")
        if m.get("near_misses"):
            body.append("<p class='note'><strong>Missed by one thing:</strong></p><ul>")
            for s in m["near_misses"]:
                body.append("<li>" + e(s) + "</li>")
            body.append("</ul>")
        if m.get("client_side_sidebar"):
            body.append("<p class='note'><strong>Client-side sidebar:</strong></p><ul>")
            for s in m["client_side_sidebar"]:
                body.append("<li>" + e(s) + "</li>")
            body.append("</ul>")
    body.append("</section>")
    return "".join(body)


# ---------------------------------------------------------------------------
# scorecard.html
# ---------------------------------------------------------------------------

SCORECARD_METRICS = [
    ("composition_violations", "Composition violations", "== 0"),
    ("quote_drop_rate", "Quote drop rate", "informational"),
    ("grade_precision", "Grade precision", ">= 0.90"),
    ("residence_precision", "Residence precision", "informational"),
    ("delivered_over_pool", "Delivered / pool", "informational"),
    ("cost_per_delivered_card", "Cost per delivered card (EUR)", "informational"),
]


def render_scorecard(snap: RunSnapshot, campaign_id: str, page_status: dict) -> str:
    body = ['<section class="block"><h2>Scorecard</h2>'
           '<p class="sub">Six numbers from eval/scorecard.py, computed against '
           "labelled ground truth.</p>"]
    sc = snap.scorecard
    if sc is None:
        body.append(
            '<p class="empty">No scorecard.json yet -- no labels have been '
            "entered for this campaign. The six metrics this page will show "
            "once labelling starts:</p><ul>"
            + "".join("<li><code>" + e(k) + "</code> -- " + e(label) + "</li>"
                     for k, label, _ in SCORECARD_METRICS)
            + "</ul></section>"
        )
        return "".join(body)
    body.append('<div class="tbl-wrap"><table class="tb"><thead><tr>'
               "<th>Metric</th><th>Value</th><th>Ship threshold</th></tr></thead><tbody>")
    for key, label, threshold in SCORECARD_METRICS:
        value = sc.get(key)
        body.append(
            "<tr><td>" + e(label) + "</td><td>"
            + (e(value) if value is not None else "<span class='empty' style='padding:0;border:0'>not computed</span>")
            + "</td><td>" + e(threshold) + "</td></tr>"
        )
    body.append("</tbody></table></div></section>")
    return "".join(body)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def render_console(
    campaign_id: str,
    out_dir,
    run_dir=None,
    page_status: Optional[dict] = None,
) -> Path:
    """Render every console page for `campaign_id` into `out_dir`.

    `run_dir` overrides where stage JSON is read from -- default is
    `run/<campaign_id>/` under this package, exactly like run.py's own
    RUN_DIR. Tests pass a fixture directory here so nothing under `run/`
    needs to exist for the console to be exercised.
    """
    out_dir = Path(out_dir)
    run_dir = Path(run_dir) if run_dir is not None else (PKG_ROOT / "run" / campaign_id)
    page_status = dict(_default_page_status(), **(page_status or {}))
    out_dir.mkdir(parents=True, exist_ok=True)

    snap = RunSnapshot(run_dir)
    role_links_all = _role_links()

    def write(name: str, html_body: str) -> None:
        (out_dir / (name + ".html")).write_text(
            # data-campaign lets the shortlist/card page's inline scripts read
            # the campaign id without templating it into every fetch() call.
            html_body.replace("<body>", "<body data-campaign='" + e(campaign_id) + "'>", 1)
            if "<body>" in html_body else html_body,
            encoding="utf-8",
        )

    write("index", _shell(
        "Today", "index", "index", page_status, campaign_id, snap.health,
        role_links_all, render_index(snap, campaign_id, page_status),
    ))
    write("jobs", _shell(
        "Jobs", "jobs", "jobs", page_status, campaign_id, snap.health,
        role_links_all, render_jobs(snap, campaign_id, page_status),
    ))
    for spec in (ROLE1, ROLE2):
        write("shortlist_" + spec.role_id, _shell(
            spec.title, "shortlist", "shortlist", page_status, campaign_id, snap.health,
            [(h, l) for h, l in role_links_all if spec.role_id in h],
            render_shortlist(snap, spec, campaign_id, page_status),
        ))
    for pid in snap.persons:
        write("card_" + pid, _shell(
            snap.persons[pid].get("full_name", pid), "card", "card", page_status,
            campaign_id, snap.health, role_links_all,
            render_card(snap, pid, campaign_id, page_status),
        ))
    write("poolmap", _shell(
        "Pool map", "poolmap", "poolmap", page_status, campaign_id, snap.health,
        role_links_all, render_poolmap(snap, campaign_id, page_status),
    ))
    write("scorecard", _shell(
        "Scorecard", "scorecard", "scorecard", page_status, campaign_id, snap.health,
        role_links_all, render_scorecard(snap, campaign_id, page_status),
    ))

    print("console: rendered " + str(2 + 2 + len(snap.persons) + 2) + " pages -> " + str(out_dir))
    return out_dir


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Render the Gaia operator console")
    ap.add_argument("--campaign-id", default=CONFIG.campaign_id)
    ap.add_argument(
        "--out-dir", default=None,
        help="defaults to deliverables/<campaign_id>/console/ under the workspace root",
    )
    args = ap.parse_args()
    out_dir = Path(args.out_dir) if args.out_dir else (
        WORKSPACE_ROOT / "deliverables" / args.campaign_id / "console"
    )
    render_console(args.campaign_id, out_dir)
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())

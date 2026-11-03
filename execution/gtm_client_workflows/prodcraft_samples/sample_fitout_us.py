"""
sample_fitout_us.py
description: Content for the US office fit-out bid proposal sample (fictional, Chicago, 14,000 sq ft).
inputs: none (all content is fictional and defined here).
outputs: render.Doc via build().
"""
from render import Doc, table, money, built_from, gantt

BRIEF = ("Tandrevo Logistics is taking floors 11 and 12 at 400 W Ardmore Place, Chicago, about 14,000 sq ft. "
         "Architect's CDs attached (open office, 8 private offices, 4 conference rooms, café). We need to be moved in "
         "by May 2027. Please send your bid with alternates and schedule.")

SF = 14_000
TRADES = [
    ("02", "Selective demolition", 68_500),
    ("06", "Carpentry & architectural millwork", 142_000),
    ("08", "Doors, frames & hardware", 96_400),
    ("08", "Interior glass & glazing", 188_000),
    ("09", "Metal framing, drywall & acoustical ceilings", 412_000),
    ("09", "Flooring (carpet tile, LVT, porcelain tile)", 164_500),
    ("09", "Painting & wallcovering", 72_800),
    ("10", "Specialties (toilet accessories, signage, markerboards)", 21_600),
    ("12", "Window treatments", 18_900),
    ("21", "Fire protection (sprinkler modifications)", 58_800),
    ("22", "Plumbing", 96_000),
    ("23", "HVAC", 318_000),
    ("26", "Electrical, lighting & low-voltage rough-in", 352_000),
    ("28", "Fire alarm modifications", 34_500),
]
TRADE_SUB = sum(t[2] for t in TRADES)
GEN_COND = 186_000
INSURANCE = round((TRADE_SUB + GEN_COND) * 0.012)
FEE = round((TRADE_SUB + GEN_COND + INSURANCE) * 0.045)
TOTAL = TRADE_SUB + GEN_COND + INSURANCE + FEE

ALTERNATES = [
    ("Alt 1", "Add", "Demountable glass-front partitions in lieu of drywall at 8 private offices", 46_200),
    ("Alt 2", "Add", "Premium broadloom carpet with cushion in executive suite and boardroom (2,100 sq ft)", 18_400),
    ("Alt 3", "Deduct", "Retain and refurbish existing ceiling grid on floor 12; new tile only", -31_500),
]


def build() -> Doc:
    d = Doc("fitout_us_bid_proposal", "Bid Proposal · Tandrevo Logistics, Floors 11–12", "Brannick Hale Builders", "letter", "#3d4a5c")

    facts = [
        ("Project", "Tenant interior fit-out, floors 11 and 12"),
        ("Address", "400 W Ardmore Place, Chicago, IL (fictional)"),
        ("Area", f"{SF:,} sq ft across two floors"),
        ("Bid documents", "Architect's CDs dated 14 Oct 2026, Addenda 1–2"),
        ("Contract form", "AIA A102 (cost of work plus fee, with GMP)"),
        ("Move-in target", "Monday 10 May 2027"),
    ]
    d.add(f"""
<div>
  <div class="kicker">Bid proposal · No. BHB-2611-07 · 3 November 2026</div>
  <h1>Office fit-out, floors 11–12<br>for Tandrevo Logistics</h1>
  <p class="lede">A complete bid for the 14,000 sq ft interior build-out, with three alternates, a schedule to a 10 May 2027 move-in, and the clarifications behind every number.</p>
</div>
<div class="grid2" style="align-items:stretch">
  <div class="card tint stat"><div class="k">Base bid (GMP)</div><div class="n">{money(TOTAL)}</div>
    <p class="small" style="margin:4px 0 0">{money(TOTAL / SF)} per sq ft · valid 45 days</p></div>
  <div class="card tint stat"><div class="k">Substantial completion</div><div class="n">30 Apr 2027</div>
    <p class="small" style="margin:4px 0 0">22 weeks from notice to proceed on 30 Nov 2026</p></div>
</div>
{table(["", ""], facts, cls="kv", align=["l","l"], widths=["28%","72%"])}
<div class="meta"><div>Prepared for<b>Facilities Director, Tandrevo Logistics</b></div><div>Prepared by<b>Project Executive, Brannick Hale Builders</b></div></div>
{built_from(BRIEF)}""", "cover")

    d.add("""
<div class="kicker">01 · Scope of work</div>
<h2>What we will build</h2>
<p class="lede">The work covers a full interior build-out of floors 11 and 12 per the architect's construction documents. Base building core, shell and restrooms are by the landlord and outside this bid.</p>
<div class="grid2">
<div>
<h3>Floor 11 · about 7,200 sq ft</h3>
<ul><li>Reception and waiting area with feature millwork desk and a glass wall to the café.</li>
<li>Café and pantry: millwork, solid-surface counters, sink, dishwasher and ice-maker connections.</li>
<li>Two conference rooms (12 and 8 seats) with acoustic insulation to deck and AV backing.</li>
<li>Open office for 44 workstations; furniture by owner, power and data poke-throughs by us.</li></ul>
<h3>Floor 12 · about 6,800 sq ft</h3>
<ul><li>Eight private offices with glass fronts and sliding doors.</li>
<li>Boardroom (16 seats) and one 6-seat conference room.</li>
<li>Open office for 38 workstations, two phone rooms, IDF room with dedicated cooling.</li></ul>
</div>
<div>
<h3>Building systems</h3>
<ul><li><b>HVAC:</b> extend base-building VAV distribution, 22 new VAV boxes with controls tied to the BAS, supplemental split system for the IDF.</li>
<li><b>Electrical:</b> new panelboards from the base-building riser, LED lighting with occupancy and daylight controls, floor boxes in conference rooms.</li>
<li><b>Plumbing:</b> café and pantry fixtures off the existing wet column.</li>
<li><b>Fire protection:</b> relocate and add heads to suit the new layout; fire alarm devices added per code.</li></ul>
<h3>Throughout</h3>
<ul><li>Full-time superintendent on site, daily cleanup, weekly owner meeting and three-week look-ahead.</li>
<li>Permit expediting with the City of Chicago Department of Buildings.</li>
<li>Close-out: as-builts, O&amp;M manuals, warranties and a punch list closed within 10 working days.</li></ul>
</div>
</div>""")

    rows = [[c, n, money(v)] for c, n, v in TRADES]
    rows += [
        (["", "Trade subtotal", money(TRADE_SUB)], "sub"),
        (["01", "General conditions (22 weeks: supervision, temp facilities, hoisting, cleanup)", money(GEN_COND)], ""),
        (["", "Insurance (general liability and builder's risk, 1.2%)", money(INSURANCE)], ""),
        (["", "Contractor's fee (4.5%)", money(FEE)], ""),
        (["", "<b>Base bid total (GMP)</b>", f"<b>{money(TOTAL)}</b>"], "total"),
        (["", f"Cost per sq ft ({SF:,} sq ft)", money(TOTAL / SF)], "muted"),
    ]
    d.add(f"""
<div class="kicker">02 · Price summary</div>
<h2>Base bid by trade</h2>
<p class="lede">Every line is based on subcontractor bids received on 28 October 2026, leveled against the CDs. Illustrative USD figures.</p>
{table(["Div.", "Trade", "Amount"], rows, align=["l","l","r"], widths=["8%","72%","20%"])}
<p class="small">Permit fees and sales tax on materials are included. Owner contingency is not included and is recommended at 5% of the base bid.</p>""")

    alt_rows = [[a, t, desc, money(v, signed=True)] for a, t, desc, v in ALTERNATES]
    excl = ["Furniture, workstations and their installation", "Audio-visual equipment and IT/telecom cabling (rough-in and backing included)",
            "Security and access control hardware (conduit and back boxes included)", "Landlord base-building work, core restrooms and code upgrades outside the demised premises",
            "Hazardous material testing or abatement", "Building permit plan review delays beyond 6 weeks", "Overtime or after-hours work except where noted",
            "Moving, artwork, plants and signage beyond the code-required items", "Utility costs during construction (assumed provided by landlord)"]
    d.add(f"""
<div class="kicker">03 · Alternates</div>
<h2>Options you can add or take out</h2>
{table(["No.", "Type", "Description", "Change to base bid"], alt_rows, align=["l","l","l","r"], widths=["9%","10%","61%","20%"])}
<p class="small">Base bid with all three alternates accepted: <b>{money(TOTAL + sum(a[3] for a in ALTERNATES))}</b>. Alternates are priced independently and can be accepted in any combination within 21 days of the bid date without affecting schedule.</p>
<div class="kicker" style="margin-top:14px">04 · Exclusions</div>
<h2>Not included in this bid</h2>
<ul>{''.join(f'<li>{e}</li>' for e in excl)}</ul>""")

    clar = [
        "Work is based on the architect's CDs dated 14 October 2026 and Addenda 1–2. Changes after that date are priced as change orders.",
        "Normal working hours are 7:00 am to 3:30 pm, Monday to Friday. Core drilling and noisy work after hours is included at 40 hours, as required by the landlord's rules.",
        "The landlord provides one freight elevator for our exclusive use 6:00–7:00 am and 3:30–6:00 pm, and shared use in between.",
        "The base-building HVAC, electrical riser and fire alarm panel have capacity for the design as drawn. Upgrades found needed are not included.",
        "Long-lead items (glass fronts, light fixtures, VAV boxes) are released on notice to proceed. Pricing assumes release by 7 December 2026.",
        "Floor flatness is assumed within the tolerance for the specified flooring. Floor prep is included up to 3,000 sq ft of skim coat.",
        "Allowances: millwork hardware $6,500 and signage $4,000, included in the trade lines above and reconciled at close-out.",
        "Owner-furnished items are delivered and stored by the owner; we coordinate delivery windows.",
        "Unused general conditions and unused allowances are returned to the owner under the GMP.",
    ]
    d.add(f"""
<div class="kicker">05 · Assumptions & clarifications</div>
<h2>What this price is based on</h2>
<ol style="padding-left:18px;margin:0">{''.join(f'<li style="margin-bottom:7px">{c}</li>' for c in clar)}</ol>
<div class="card tint" style="margin-top:12px"><p style="margin:0"><b>Open item for owner decision.</b> Café appliance package: the CDs show owner-furnished appliances. If you would like us to supply them, we will price it as an alternate within 3 working days.</p></div>""")

    periods = ["Dec", "", "Jan", "", "Feb", "", "Mar", "", "Apr", "", "May", ""]
    sub = ["1–15", "16–31", "1–15", "16–31", "1–14", "15–28", "1–15", "16–31", "1–15", "16–30", "1–15", "16–31"]
    tasks = [
        ("Notice to proceed, submittals, long-lead release", 0, 1),
        ("Building permit (review + issue)", 0, 3),
        ("Selective demolition", 4, 4),
        ("Framing, MEP rough-in, inspections", 5, 6),
        ("Drywall, glazing frames, ceiling grid", 6, 7),
        ("Millwork, doors, finishes, flooring", 7, 8),
        ("MEP trim, commissioning, fire alarm test", 8, 8),
        ("Punch list, final inspection, occupancy", 9, 9),
        ("Furniture install and IT (owner)", 9, 10),
        ("Move-in (10 May 2027)", 10, 10),
    ]
    d.add(f"""
<div class="kicker">06 · Schedule</div>
<h2>22 weeks to substantial completion</h2>
<p class="lede">Notice to proceed 30 November 2026. Substantial completion 30 April 2027. Ten days of buffer before move-in on 10 May 2027.</p>
{gantt(periods, tasks, sub=sub)}
<div class="grid3" style="margin-top:8px">
  <div class="card tint"><p style="margin:0"><b>Critical path.</b> Permit issue by 29 January 2027. A two-week slip moves completion by about one week; we recover the rest with a second framing crew.</p></div>
  <div class="card tint"><p style="margin:0"><b>Long lead.</b> Glass fronts 12 weeks, light fixtures 10 weeks, VAV boxes 8 weeks from release.</p></div>
  <div class="card tint"><p style="margin:0"><b>Phasing.</b> Both floors run together; floor 12 finishes first so furniture install can start a week early.</p></div>
</div>""")

    d.add(f"""
<div class="kicker">07 · Terms & validity</div>
<h2>Commercial terms</h2>
<ul>
<li><b>Validity.</b> This bid is valid for 45 days from 3 November 2026. Subcontractor pricing on glazing and electrical is held to that date only.</li>
<li><b>Contract.</b> AIA A102 with A201 general conditions, as modified by mutual agreement. GMP {money(TOTAL)} for the base bid plus accepted alternates.</li>
<li><b>Payment.</b> Monthly progress billing on AIA G702/G703, net 30. Retainage 10% to 50% complete, then 5%, released at substantial completion less punch-list value.</li>
<li><b>Changes.</b> Priced at cost plus the 4.5% fee and 1.2% insurance, with backup, before work proceeds.</li>
<li><b>Warranty.</b> One year on workmanship from substantial completion; manufacturer warranties passed through.</li>
<li><b>Insurance.</b> Certificates naming owner and landlord as additional insured, delivered before mobilization.</li>
</ul>
<div class="kicker" style="margin-top:12px">Acceptance</div>
<p>Signing below accepts the base bid of <b>{money(TOTAL)}</b> and the alternates marked, subject to execution of the contract above.</p>
{table(["Alternate", "Accept", "Decline"], [[f"{a} · {t} {money(v, signed=True)}", "☐", "☐"] for a, t, _, v in ALTERNATES], align=["l","c","c"], widths=["60%","20%","20%"])}
<div class="sig">
  <div><div class="line"></div><div class="lab">For Tandrevo Logistics · name, title</div><div class="line"></div><div class="lab">Signature · date</div></div>
  <div><div class="line"></div><div class="lab">For Brannick Hale Builders · name, title</div><div class="line"></div><div class="lab">Signature · date</div></div>
</div>""")
    return d
